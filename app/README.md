# DnD Engine API

A FastAPI application that exposes the DnD Engine entity registry.

## Project Structure

```
app/
├── api/                  # API package
│   ├── deps.py           # Shared dependencies
│   └── routes/           # API routes
│       └── entities.py   # Entity endpoints
├── main.py               # Application entry point and configuration
├── README.md             # This file
└── run_server.py         # Server runner script
```

## Getting Started

### Prerequisites

- Python 3.9+
- FastAPI
- Uvicorn
- Pydantic

### Installation

Install the required dependencies:

```bash
pip install fastapi uvicorn pydantic
```

### Running the Server

Run the server using the provided script:

```bash
python app/run_server.py
```

Or directly with uvicorn:

```bash
cd app
uvicorn main:app --reload
```

The server will start on http://localhost:8000

## API Endpoints

### List all entities

```
GET /api/entities/
```

Returns a list of all entities in the registry with their UUIDs and names.

### Get entity by UUID

```
GET /api/entities/{entity_uuid}
```

Parameters:
- `include_skill_calculations` (boolean, optional): Include detailed skill calculations
- `include_attack_calculations` (boolean, optional): Include detailed attack calculations
- `include_ac_calculation` (boolean, optional): Include detailed AC calculation

Returns the complete entity snapshot.

### Get specific subblock of an entity

```
GET /api/entities/{entity_uuid}/{subblock_name}
```

Available subblocks:
- `health`
- `ability_scores`
- `skill_set`
- `equipment`
- `saving_throws`
- `proficiency_bonus`

Returns the requested subblock snapshot.

## Interactive Documentation

Once the server is running, you can access the interactive API documentation at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc 