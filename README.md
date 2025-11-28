# Geofence Event Processing System

A scalable, reliable, and efficient location-based service for taxi companies that tracks vehicles as they move through different geographic zones and detects zone boundary crossings using GPS coordinates.

## 🏗️ Architecture Overview

This system is built with modern, scalable technologies:

- **Backend**: Django REST Framework with Python
- **Database**: Azure Cosmos DB (Serverless) for high-performance, globally distributed data storage
- **Geospatial Processing**: ArcGIS API for Python + ArcGIS JavaScript API for US state-level geofencing
- **Caching**: Redis with Django-Redis for high-performance caching
- **Frontend**: HTML with Tailwind CSS, Alpine.js, and ArcGIS JavaScript API for real-time dashboard
- **Monitoring**: Built-in health checks and comprehensive logging

## 🚀 Key Features

### Core Functionality
- **Real-time Location Processing**: Accept GPS location events via HTTP endpoints
- **ArcGIS State-Level Geofencing**: Detect vehicle entry/exit events using ArcGIS spatial queries
- **Vehicle Status Queries**: Query current zone status for any vehicle
- **US Multi-State Taxi Simulation**: 5 taxis traveling across US states with real-time tracking

### Advanced Features
- **ArcGIS Integration**: Uses ArcGIS REST API for accurate point-in-polygon state detection
- **Real-time Dashboard**: Live visualization with ArcGIS JavaScript API showing:
  - Taxi positions with colored markers
  - Dropoff destinations with 📍 pin markers
  - Route lines connecting taxis to destinations
  - State boundary overlays
- **Zone Entry/Exit Notifications**: Real-time toast notifications and trace log
- **Taxi Search by Zone**: Find taxis currently in a specific state
- **Multi-layer Caching**: Redis caching for optimal performance

## 🛠️ Technology Stack

### Backend
- **Django 5.2.8**: Web framework
- **Django REST Framework**: API development
- **Azure Cosmos DB (Serverless)**: NoSQL database for geospatial data
- **ArcGIS API for Python 2.4.2**: State-level geofencing
- **Redis**: Caching layer
- **Structlog**: Structured logging

### Frontend
- **Tailwind CSS**: Utility-first CSS framework
- **Alpine.js**: Lightweight JavaScript framework
- **ArcGIS JavaScript API 4.28**: Interactive maps with state boundaries

### Infrastructure
- **Azure Cosmos DB**: Globally distributed database (Serverless mode)
- **Redis**: In-memory data structure store
- **ArcGIS Sample Server**: US state boundaries layer

## 📋 Prerequisites

- Python 3.9+ (Python 3.13 recommended)
- Redis server (optional, for caching)
- Azure Cosmos DB account (Serverless)
- Git

## 🚀 Quick Start - Unzipping the Project
### Step 1: 
Open "geofence_event_processing_project" project in IDE

### Step 2:
Open README.md file for detail steps / follow below steps.

### Step 3: 
After creating virtual environment and installing dependencies, create database and container in Azure Cosmos DB, and fill the details in .env file.


## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone <repository-url>
cd geofence_event_processing_project
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
Create a `.env` file with your Azure Cosmos DB credentials:
```env
# Azure Cosmos DB Configuration (Serverless)
COSMOS_ENDPOINT=https://your-cosmos-account.documents.azure.com:443/
COSMOS_KEY=your-cosmos-key
COSMOS_DATABASE_NAME=geofence-data
COSMOS_CONTAINER_NAME=taxi

# Django Configuration
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Redis Configuration (optional)
REDIS_URL=redis://127.0.0.1:6379/1
```

### 5. Initialize Database
```bash
python manage.py migrate
```

### 6. Start the Server
```bash
python manage.py runserver
```

### 7. Access the Dashboard
- **US Taxi Dashboard**: `http://localhost:8000/`

## 📡 API Documentation

### ArcGIS Simulation API (v2)

#### POST `/api/v2/simulation/start/`
Start the US multi-state taxi simulation.

#### POST `/api/v2/simulation/stop/`
Stop the taxi simulation.

#### GET `/api/v2/simulation/status/`
Get current simulation status and all taxi positions.

**Response:**
```json
{
    "simulation_running": true,
    "total_taxis": 5,
    "taxis": {
        "taxi_a": {
            "taxi_id": "taxi_a",
            "current_position": {"latitude": 41.58, "longitude": -71.47},
            "current_zone": "Rhode Island",
            "status": "pickup",
            "route_progress": 0.45,
            "current_route": {
                "pickup": {"state": "Rhode Island", "coordinates": [41.58, -71.47]},
                "dropoff": {"state": "Massachusetts", "coordinates": [42.40, -71.38]}
            }
        }
    }
}
```

#### GET `/api/v2/simulation/search/?zone={state_name}`
Search for taxis in a specific state/zone.

### Location Event Processing (v1)

#### POST `/api/v1/events/location/`
Process incoming GPS location events from vehicles.

**Request Body:**
```json
{
    "vehicle_id": "taxi_001",
    "latitude": 40.7589,
    "longitude": -73.7804,
    "timestamp": "2024-01-01T12:00:00Z"
}
```

## 🚖 Taxi Simulation

The system includes 5 taxis with predefined routes across US states:

| Taxi | Pickup State | Dropoff State | Distance |
|------|--------------|---------------|----------|
| Taxi A | Rhode Island | Massachusetts | ~92 km |
| Taxi B | Tennessee | Alabama | ~357 km |
| Taxi C | Idaho | Montana | ~463 km |
| Taxi D | New York | Connecticut | ~210 km |
| Taxi E | Texas | New Mexico | ~581 km |

### Taxi Colors on Map
- 🔴 **Taxi A**: Red
- 🟢 **Taxi B**: Green
- 🔵 **Taxi C**: Blue
- 🟠 **Taxi D**: Orange
- 🟣 **Taxi E**: Purple

## 🗺️ ArcGIS Geofencing

### How It Works
1. **State Detection**: Uses ArcGIS REST API spatial queries to determine which US state a coordinate is in
2. **Real-time Classification**: Each taxi position is classified in real-time using point-in-polygon queries
3. **Zone Events**: Entry/exit events are generated when taxis cross state boundaries

### ArcGIS Services Used
- **State Boundaries**: `https://sampleserver6.arcgisonline.com/arcgis/rest/services/USA/MapServer/2`
- **Frontend Map**: ArcGIS JavaScript API 4.28 with `streets-navigation-vector` basemap

## 📁 Project Structure

```
geofence_event_processing_project/
├── arcgis_geofence_service.py    # ArcGIS geofencing logic
├── geofence_app/                  # Main Django app
│   ├── arcgis_views.py           # ArcGIS API endpoints
│   ├── arcgis_urls.py            # ArcGIS URL routing
│   ├── taxi_simulation_views.py  # Simulation control
│   ├── cosmos_service.py         # Cosmos DB operations
│   └── views.py                  # Core API views
├── templates/
│   └── us_taxi_dashboard.html    # ArcGIS-based dashboard
├── requirements.txt              # Python dependencies
├── manage.py                     # Django management
└── .env                          # Environment configuration
```

## 🎯 Design Decisions

### Why ArcGIS over H3?
1. **Accurate State Boundaries**: ArcGIS provides actual US state polygon boundaries
2. **No Pre-computation**: Real-time spatial queries without pre-indexing
3. **Visual Integration**: ArcGIS JavaScript API provides professional map visualization
4. **Reliable Public Services**: Uses Esri's sample server for state boundaries

### Why Azure Cosmos DB Serverless?
1. **Pay-per-request**: Cost-effective for variable workloads
2. **No Throughput Management**: No need to configure RU/s
3. **Auto-scaling**: Handles traffic spikes automatically
4. **Global Distribution**: Low latency worldwide

## ⚠️ Assumptions & Tradeoffs

### Sample Data Assumptions

This project uses **sample/demo data** for demonstration purposes:

| Data Type | Sample Size | Notes |
|-----------|-------------|-------|
| **Taxis** | 5 vehicles | Taxi A through E with predefined routes |
| **States** | 10 US states | Rhode Island, Massachusetts, Tennessee, Alabama, Idaho, Montana, New York, Connecticut, Texas, New Mexico |
| **Routes** | 5 fixed routes | Each taxi has a single pickup → dropoff route that loops continuously |
| **GPS Coordinates** | Hardcoded | Real city coordinates within each state (e.g., Providence RI, Boston MA) |

### Technical Assumptions

1. **Continental US Only**: Taxis operate within the continental United States; Alaska, Hawaii, and territories are not included
2. **WGS84 Coordinates**: All GPS coordinates use WGS84 (EPSG:4326) format, the standard for GPS devices
3. **Network Connectivity**: Requires internet access for ArcGIS API spatial queries
4. **Cosmos DB Partition Key**: The `taxi` container uses `id` as the partition key
5. **Single Instance**: Designed for single-server deployment; distributed deployment would require additional configuration

### Design Tradeoffs

| Decision | Tradeoff | Rationale |
|----------|----------|-----------|
| **5 Taxis (not 1000s)** | Limited scale demo | Keeps ArcGIS API calls manageable; demonstrates core functionality without rate limiting issues |
| **Fixed Routes** | No dynamic routing | Simplifies simulation; real system would integrate with routing APIs |
| **Polling (2s interval)** | Not real-time WebSocket | Simpler implementation; WebSocket would reduce latency but add complexity |
| **ArcGIS Sample Server** | Dependent on external service | Free, reliable, no API key required; production would use dedicated ArcGIS service |
| **In-Memory Simulation** | State lost on restart | Fast performance; production would persist simulation state to database |
| **10x Speed Multiplier** | Unrealistic taxi speeds | Faster demo progression; real system would use actual travel times |

### What Would Change in Production

| Demo Implementation | Production Implementation |
|---------------------|---------------------------|
| 5 hardcoded taxis | Dynamic fleet from database |
| Fixed pickup/dropoff points | Real-time dispatch system integration |
| ArcGIS Sample Server | Licensed ArcGIS Enterprise or Azure Maps |
| Polling every 2 seconds | WebSocket real-time updates |
| SQLite for Django | PostgreSQL with PostGIS |
| Single server | Kubernetes with auto-scaling |
| No authentication | OAuth2/JWT authentication |

### Known Limitations

1. **ArcGIS Rate Limits**: The public ArcGIS Sample Server may throttle requests under heavy load
2. **No Offline Support**: Requires continuous internet connectivity
3. **No Route Optimization**: Taxis travel in straight lines, not actual road networks
4. **Single Timezone**: All timestamps are in UTC; no timezone localization
5. **No Historical Replay**: Cannot replay past taxi movements (only current state)

## 🔧 Configuration Files

### Required Files
1. **`.env`** - Environment variables (see Quick Start)
2. **`requirements.txt`** - Python dependencies

### Optional Files
- **`docker-compose.yml`** - Docker deployment
- **`nginx.conf`** - Production reverse proxy

## 📊 Monitoring

### Health Check
```
GET /health/
```

### Logging
Logs are stored in `logs/geofence.log` with levels:
- **INFO**: Normal operations
- **WARNING**: Non-critical issues
- **ERROR**: Failures requiring attention

## 🚀 Deployment

### Production Checklist
1. Set `DEBUG=False`
2. Configure `ALLOWED_HOSTS`
3. Use HTTPS
4. Set up proper Cosmos DB indexing
5. Configure Redis for caching (optional)

## 🔮 Future Improvements (Given More Time)

### Performance
- **WebSocket Support**: Replace polling with real-time WebSocket updates
- **Batch Processing**: Process multiple location updates in single requests
- **Caching Layer**: Cache ArcGIS spatial query results for frequently accessed areas

### Features
- **Route Visualization**: Show actual driving routes on map (not just straight lines)
- **Historical Playback**: Replay taxi movements over time
- **Analytics Dashboard**: Charts showing zone dwell times, trip statistics
- **Multi-tenant Support**: Support multiple taxi companies with isolated data

### Architecture
- **Message Queue**: Use Azure Service Bus for async event processing
- **Microservices**: Split into separate services for simulation, geofencing, storage
- **Event Sourcing**: Store all location events for complete audit trail

### Testing
- **Load Testing**: Simulate thousands of concurrent taxis
- **Integration Tests**: End-to-end API testing
- **Chaos Engineering**: Test failure scenarios

### DevOps
- **CI/CD Pipeline**: Automated testing and deployment
- **Kubernetes**: Container orchestration for scaling
- **Monitoring**: Application Performance Monitoring (APM)

## 📄 License

This project is licensed under the MIT License.
