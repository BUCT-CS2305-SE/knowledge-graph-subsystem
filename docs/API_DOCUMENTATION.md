# Knowledge Graph Subsystem - API Documentation (v1.0)

## Overview
This API provides access to the Knowledge Graph Subsystem's dual-layer storage (MySQL for detailed structural queries, Neo4j for relationship and graph traversal). It is designed to support frontend development teams in building immersive, theme-based artifact browsing (e.g., Ceramics, Jade, Painting) and visualization experiences.

## Security & Authentication
- **Base URL:** `https://api.yourdomain.com/v1`
- **Authentication:** All requests must include an API Key in the header.
  - Header: `X-API-Key: <your_api_key_here>`
- **Rate Limiting:** 100 requests per minute per IP to prevent service abuse.

---

## 1. Artifact Browsing & Query APIs (Powered by MySQL)

### 1.1 Get Artifact List
Retrieve a paginated list of artifacts, allowing theme-based filtering.

**Endpoint:** `GET /artifacts`

**Query Parameters:**
| Parameter | Type   | Required | Description |
| :--- | :--- | :--- | :--- |
| `page` | int | No | Page number (default: 1) |
| `limit` | int | No | Items per page (default: 20, max: 100) |
| `type` | string | No | Theme filter (e.g., `Ceramics`, `Jade`, `Painting`, `Bronze`) |
| `period` | string | No | Dynasty/Period filter (e.g., `Tang Dynasty`, `Qing Dynasty`) |
| `museum` | string | No | Museum name filter |

**Success Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "total": 1500,
    "page": 1,
    "limit": 20,
    "items": [
      {
        "object_id": "25247",
        "title": "Tree Peonies in Full Bloom",
        "type": "Painting",
        "period": "Qing Dynasty (1644-1911)",
        "image_url": "https://.../default.jpg",
        "museum": "Art Institute of Chicago"
      }
    ]
  }
}
```

### 1.2 Get Artifact Details
Retrieve detailed structured information about a specific artifact for immersive display.

**Endpoint:** `GET /artifacts/{object_id}`

**Success Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "object_id": "25247",
    "title": "Tree Peonies in Full Bloom",
    "period": "Qing Dynasty (1644-1911)",
    "type": "Painting",
    "material": "Hanging scroll; ink and colors on silk",
    "description": "This painting depicts...",
    "dimensions": "116.8 × 59.7 cm",
    "museum": "Art Institute of Chicago",
    "location": "Chicago, USA",
    "image_url": "https://.../default.jpg",
    "detail_url": "https://www.artic.edu/artworks/25247"
  }
}
```

---

## 2. Knowledge Graph APIs (Powered by Neo4j)

### 2.1 Get Artifact Graph Context (1-Hop Ego Graph)
Retrieve the graph nodes and relationships surrounding a specific artifact for network visualization.

**Endpoint:** `GET /graph/artifact/{object_id}`

**Success Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "nodes": [
      { "id": "obj_25247", "label": "Artifact", "title": "Tree Peonies in Full Bloom" },
      { "id": "loc_chicago", "label": "Museum", "name": "Art Institute of Chicago" },
      { "id": "per_qing", "label": "Period", "name": "Qing Dynasty (1644-1911)" },
      { "id": "typ_paint", "label": "Type", "name": "Painting" }
    ],
    "edges": [
      { "source": "obj_25247", "target": "loc_chicago", "type": "STORED_IN" },
      { "source": "obj_25247", "target": "per_qing", "type": "BELONGS_TO_PERIOD" },
      { "source": "obj_25247", "target": "typ_paint", "type": "HAS_TYPE" }
    ]
  }
}
```

### 2.2 Get Period Context (Augmented Data)
Retrieve rich background information for a historical period to provide immersive storytelling.

**Endpoint:** `GET /graph/period/{period_name}`

**Success Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "name": "Qing Dynasty (1644-1911)",
    "uri": "http://knowledge-graph.system/entity/period/Qing...",
    "description": "清朝（1644年—1912年）是中国历史上最后一个封建王朝...",
    "source": "Baidu Baike"
  }
}
```

## Error Handling
Standard HTTP status codes are used. Error responses follow this format:
```json
{
  "status": "error",
  "code": 404,
  "message": "Artifact not found"
}
```
