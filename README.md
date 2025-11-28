# Geofence Event Processing System

A scalable, reliable, and efficient location-based service for taxi companies that tracks vehicles as they move through different geographic zones and detects zone boundary crossings using GPS coordinates.

## 🏗️ Architecture Overview

This system is built with modern, scalable technologies:

- **Backend**: Django REST Framework with Python
- **Database**: Azure Cosmos DB (Serverless) for high-performance, globally distributed data storage
- **Geospatial Processing**: ArcGIS API for Python + ArcGIS JavaScript API for US state-level geofencing

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
Create a `.env` file in root directory with your Azure Cosmos DB credentials:
```env
# Azure Cosmos DB Configuration (Serverless)
COSMOS_ENDPOINT=https://your-cosmos-account.documents.azure.com:443/
COSMOS_KEY=your-cosmos-key
COSMOS_DATABASE_NAME=your_database_name
COSMOS_CONTAINER_NAME=your_container_name

# Django Configuration
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1


### 5. Initialize Database
```bash
python manage.py migrate
```

### 6. Start the Server
```bash
python manage.py runserver
```

### 7. Access the Dashboard
- **Geofence Taxi Dashboard (ArcGIS)**: `http://localhost:8000/`

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

### Assumptions
1. Taxis operate within the continental United States
2. GPS coordinates are in WGS84 (EPSG:4326) format
3. Network connectivity is available for ArcGIS API calls
4. Cosmos DB container uses `vehicle_id` as partition key

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

