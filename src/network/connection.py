# src/network/connection.py
import time
import queue
import socket
import threading
from typing import Callable, Optional, List, Dict, Any
from src.network.messages import Message

class ConnectionHandler:
    def __init__(self):
        self.read_buffer = bytearray()
        self.write_queue = queue.Queue()
        self.callbacks = []
        self.lock = threading.RLock()
        self._running = False

    def register_callback(self, callback: Callable[[Message], None]) -> None:
        """
            Register a callback for received message.

            Args:
                callback(Callable[[Message], None])
        """
        with self.lock:
            self.callbacks.append(callback)

    def send(self, message: bytes) -> None:
        """Queue a message to be sent"""
        self.write_queue.put(message)

    def _process_read_buffer(self) -> None:
        """Process the read buffer and emit message_received events."""
        with self.lock:
            # In real-world implementation, we would need a message framing protocol
            # This is simplified
            try:
                if self.read_buffer:
                    message = Message.deserialize(bytes(self.read_buffer))
                    self.read_buffer.clear()

                    # Notify all registered callbacks
                    for callback in self.callbacks:
                        callback(message)
            except ValueError as e:
                # Message not complete or invalid, in that case,
                # we wait for more data
                pass

    def handle_received_data(self, data: bytes) -> None:
        """Add received data to the read buffer and process it."""
        with self.lock:
            self.read_buffer.extend(data)
            self._process_read_buffer()

    def get_next_message(self) -> Optional[bytes]:
        """Get the next message from the queue if available."""
        try:
            return self.write_queue.get_nowait()
        except queue.Empty:
            return None
        
    def stop(self) -> None:
        """Stop the connection handler."""
        self._running = False


class SocketWrapper:
    def __init__(self, host: str, port: int,
                 connect_timeout: float = 5.0,
                 retry_interval: float = 2.0,
                 max_retries: int = 3):
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.retry_interval = retry_interval
        self.max_retries = max_retries

        self.socket = None
        self.handler = ConnectionHandler()
        self.read_thread = None
        self.write_thread = None
        self._running = False

    def connect(self) -> bool:
        """Connect to remote host."""
        retries = 0

        while retries < self.max_retries:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(self.connect_timeout)
                self.socket.connect((self.host, self.port))
                self.socket.settimeout(None) # Set to blocking mode for read/write operations
                return True
            
            except (socket.timeout, ConnectionRefusedError, OSError) as e:
                print(f"Connection attempt {retries+1} failed: {e}!")
                if self.socket:
                    self.socket.close()
                    self.socket = None

                retries += 1
                if retries > self.max_retries:
                    return False
                
                time.sleep(self.retry_interval)
        
        return False

    def start(self) -> None:
        """Start the socket wrapper thread."""
        if not self.socket:
            raise RuntimeError("Cannot start: socket is not connected!")
        
        self._running = True
        self.handler._running = True

        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()

        self.write_thread = threading.Thread(target=self._write_loop, daemon=True)
        self.write_thread.start()

    def _read_loop(self) -> None:
        """Read loop processing incoming data."""
        while self._running and self.socket:
            try:
                data = self.socket.recv(4096)
                if not data: # Connection closed by peer
                    break
                self.handler.handle_received_data(data)
            except (socket.error, OSError):
                break

    def _write_loop(self) -> None:
        """Write loop sending queue messages."""
        while self._running and self.socket:
            message = self.handler.get_next_message()
            if message:
                try:
                    self.socket.sendall(message)
                except (socket.error, OSError):
                    break
            else:
                # No message to send, sleep to avoid CPU spin
                time.sleep(0.01)

        self._cleanup()

    def _cleanup(self) -> None:
        """Clean up resources when connection ends."""
        self._running = False
        self.handler.stop()

        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            finally:
                self.socket = None

    def send(self, message: bytes) -> None:
        """Send a messsage through the connection handler."""
        self.handler.send(message)

    def register_callback(self, callback: Callable[[Message], None]) -> None:
        """Register a callback for received messages."""
        self.handler.register_callback(callback)

    def close(self) -> None:
        """Close the connection."""
        self._running = False

        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except:
                pass
            finally:
                self.socket = None

        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=1.0)

        if self.write_thread and self.write_thread.is_alive():
            self.write_thread.join(timeout=1.0)