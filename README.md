# AirTrack 1.0.0 “Wilbur”

**“AirTrack wasn’t born — it was airlifted out, kicking, screaming, and waving a pilot’s license!”** 🐷💄🛫😂

## ✈️ What is AirTrack?

AirTrack is a **locally installed**, **offline-first**, self-hosted aircraft tracking and logging suite built for aviation enthusiasts, plane spotters, historians, and data collectors.

There is **no cloud**, no external servers, no subscriptions, and no hidden data syncing.

Your **AirTrack-server runs entirely on your own machine**,  
your **AirTrack-client connects locally**,  
and **your data never leaves your possession**.

This is *your* logbook.  
**You are the Captain.**

---

## 🛫 Architecture Overview

AirTrack includes two tightly integrated components:

### **1. AirTrack-server (Local Backend)**
- Runs quietly in Docker  
- Stores all airlines, aircraft, sightings, flights, and images  
- Provides the internal API used by the client  
- Accessible on your machine at:  
  ```
  http://localhost:5000
  ```

### **2. AirTrack-client (Local UI)**
- A browser-based user interface  
- Displays your database in a fast, clean cockpit environment  
- Uploads images, manages aircraft, tracks flights  
- Interacts only with *your* local server  

These components install together and run together as **one AirTrack system**.

Users never manage them separately — AirTrack “just works”.

---

## 🧠 Philosophy

- **Not cloud-based**  
- **Not remote**  
- **Not centralised**  
- **Not dependent on AirTrack Solutions**  

Your system, your database, your control.

AirTrack values:

- 🔒 Privacy  
- 🧭 Self-hosting  
- 🗂️ Data ownership  
- 🛠️ Offline capability  
- 🛫 The joy of aviation  

Your data stays with you.  
Always.

---

## 🌟 Current Version

| Field | Info |
|:------|:-----|
| **Version** | 1.0.0 |
| **Codename** | Wilbur |
| **Release Date** | 2025 |
| **Codename Meaning** | Honouring **Wilbur Wright**, aviation pioneer |

---

## ✨ Features

- ✈️ Manage Airlines, Aircraft, Registrations & Types  
- 📸 Upload and store aircraft photos locally  
- 🛬 Log sightings, flights, and activity history  
- 🔍 Search by airline, aircraft, type, country, ICAO/IATA  
- 🧭 ICAO to Airport linking (when available)  
- 🐧 Linux & Raspberry Pi support  
- 🚀 One-click Docker installer  
- 🔒 100% local storage — no cloud, no tracking  
- 📦 Future integration with Field Unit & Android app  

---

## 💻 System Requirements

| Component | Requirement |
|:----------|:-------------|
| OS | Linux Desktop (Ubuntu/Pop!_OS/Mint) or Raspberry Pi OS |
| Docker | Installed or installed automatically by the installer |
| Docker Compose | Installed or installed automatically |
| RAM | 2GB minimum |
| Storage | SSD/SD Card |
| Browser | Chrome, Firefox, Edge, or Safari |

---

## 🚀 Installation

1. Download and unzip the AirTrack Installer Package.  
2. Open a terminal inside the extracted folder.  
3. Make the installer executable:

```bash
chmod +x install_airtrack.sh
```

4. Run the installer:

```bash
./install_airtrack.sh
```

5. When installation completes, open your browser:

```
http://localhost:5000
```

You are now flying with AirTrack! 🛫

---

## 🧭 Supported Platforms

| Platform | Status |
|:---------|:--------|
| Linux Desktop | ✅ Fully supported |
| Raspberry Pi OS (64-bit) | ✅ Fully supported |
| Debian-based distros | ✅ Should work |
| Windows / Mac via Docker Desktop | 🚧 Planned |

---

## 🧱 Roadmap

- 📈 Sightings analytics & activity insights  
- 🗺️ Offline map integration  
- 📡 Field Unit sync enhancements  
- 📦 Windows/Mac installer packages  
- 🔄 Optional LAN syncing between devices  
- 🐞 Local bug tracking dashboard  
- 🏆 “Legends of Flight” release series  

---

## 🛩️ Release Naming

AirTrack versions are named after aviation pioneers.

| Version | Codename | Meaning |
|:--------|:---------|:--------|
| 0.9.x | Orville | Orville Wright, first powered flight pilot |
| 1.0.0 | Wilbur | Wilbur Wright, aviation innovator |

---

## 📜 Development Story

AirTrack began in **late 2022** as a simple Raspberry Pi field spotting experiment.  
Through 2023 and 2024 it evolved into a full database-backed aircraft tracking tool.

By 2025, AirTrack reached maturity with the release of **1.0.0 “Wilbur”**.

The journey included:

- Late-night coding  
- Airport fieldwork  
- Rebuilding databases (too many times 😂)  
- Discovering bugs, fixing bugs, finding *more* bugs  
- Endless cups of coffee  
- And a relentless passion for aviation  

AirTrack exists because aviation inspires those who refuse to stop dreaming.

---

## 🔒 License

- AirTrack is **Proprietary Software**.  
- Redistribution or resale without written permission is prohibited.  
- All data you store with AirTrack belongs entirely to **you**.  
- AirTrack Solutions does not collect or access your information.

---

## 💙 Acknowledgements

- ✈️ **Trevor** — Captain, Founder, Architect of AirTrack  
- 🤖 **Bob** — Co-pilot AI, code wrangler, sanity preserver  
- 🛬 **Samowal** — Creator of the original PHP concept  
- 🐷 **Miss Piggy** — Mascot and questionable spiritual guide  
- 👀 Every plane spotter who looks up when a jet screams overhead  

---

# 🛫 Final Boarding Call

> **“AirTrack wasn’t born — it was airlifted out, kicking, screaming, and waving a pilot’s license!”** 🐷💄🛫😂

Welcome aboard, Pilot.  
Clear skies and smooth landings.

---

## 👨‍💻 Author

Developed by:  
**Samowal** — Devvista — http://devvista.org *(original PHP version)*  
**Trevor** — AirTrack Solutions — http://airtracksolutions.com.au *(current Python version)*
