# Simple Torrent-like Application (STA) Specification

## Core Objectives
Develop a network application supporting multi-directional data transfer (MDDT) using TCP/IP protocol stack with two host types: tracker and node.

## System Components
### Hosts
- **Tracker**: Centralized server tracking node file pieces
- **Nodes**: Clients that share and download files

### Key Protocols
1. **Tracker Protocol**
   - Nodes report local file repository to tracker
   - Tracker provides peer list for file downloads
   - Supports started/stopped/completed request states

2. **File Transfer Protocol**
   - MDDT: Simultaneous multi-source file downloads
   - Multithreaded node implementation
   - Piece-based file transfer (recommended ~512KB pieces)

### Essential Concepts
- **Magnet Text**: Identifier linking to file metadata
- **Metainfo File**: Contains tracker address, piece details
- **Pieces**: Equally-sized file segments
- **Peer Discovery**: Obtain peer list from tracker
- **Download Strategy**: Request only unavailable pieces

### Minimum Requirements
- Single file per torrent (initial implementation)
- Peer-to-peer file sharing
- Basic upload/download statistics
- User interface for torrent management

## Extra Credit Options
- Distributed Hash Table (DHT)
- Simultaneous multiple torrent support
- Advanced download strategies
- Tracker scrape implementation
- Optimized peer selection

## Development Recommendations
- Implement request queuing
- Track piece request status
- Support file seeding
- Consider "tit-for-tat" sharing principles