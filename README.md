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
P2P File Sharing/            # root
├── data/                    # storage
├── src/                     # source code
│   ├── config.py            # configurations
│   ├── node.py              # peer node
│   ├── torrent.py           # torrent file parser
│   ├── tracker.py           # central tracker server
│   └── utils.py             # utility functions
├── tests/                   # test suite
│   └── unit_test.py         # unit tests
├── .gitignore
└── README.md
```