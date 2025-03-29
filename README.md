# P2P File-Sharing System 🌐

A BitTorrent-like peer-to-peer file-sharing system with a central tracker, supporting multi-threaded uploads/downloads and chunk-based transfers.

---

## 🛠 Setup (Python 3.8+)

### 1. Create Virtual Environment
```bash
python -m venv venv

source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate    # Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt # Install dependencies
```

---

## 📂 Project Structure
```
P2P File Sharing/
├── src/                         
│   ├── config.py                # Configurations (unchanged)
│   ├── core/                    
│   │   ├── node.py              # Main Node class (uses patterns)
│   │   └── tracker.py           # Tracker (Observer pattern)
│   ├── network/
│   │   ├── connection.py        # Connection handling (Template Method)
│   │   └── messages.py          # Message Factory pattern
│   ├── strategies/              
│   │   ├── piece_selection.py   # Strategy pattern (RarestFirst/Random)
│   │   └── choking.py           # Choke algorithm strategies
│   ├── states/                  # State pattern
│   │   ├── leecher_state.py     
│   │   └── seeder_state.py      
│   ├── torrent/                 
│   │   └── parser.py            # Torrent file parsing
│   └── utils/                   
│       ├── serialization.py     
│       └── logger.py            
├── tests/                       # Mirror src structure                  
│   ├── core/                
│   ├── network/               
│   ├── states/     
│   ├── strategies/                   
│   ├── torrent/            
│   └── unit_test.py             
├── .gitignore
└── README.md
```