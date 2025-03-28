# src/utils/serialization.py
import logging

def setup_logger(name):
    return logging.getLogger(name)

def serialize(data):
    return repr(data).encode()

def deserialize(data):
    return eval(data.decode())