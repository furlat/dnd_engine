# D&D Engine ModifiableValue Viewer

A React-based UI for viewing the hierarchical structure of ModifiableValue objects from the D&D Engine API.

## Features

- Search for ModifiableValues by UUID
- View hierarchical representation of ModifiableValue data
- Expandable/collapsible JSON-like tree view
- Summary and detailed views of components

## Getting Started

### Prerequisites

- Node.js (v14 or later recommended)
- npm or yarn
- D&D Engine API running on http://localhost:8000

### Installation

1. Navigate to the `ui` directory
2. Install dependencies:
   ```
   npm install
   ```

### Running the Application

1. Start the development server:
   ```
   npm run dev
   ```
2. Open your browser to http://localhost:5173

### Building for Production

```
npm run build
```

## Usage

1. Enter a valid ModifiableValue UUID in the search bar
2. The app will fetch and display the data in a hierarchical format
3. Use the expand/collapse toggles to explore the data structure

## API Integration

The application expects the D&D Engine API to be running on http://localhost:8000 with the following endpoints:
- `GET /api/values/:uuid` - Returns detailed information about a specific ModifiableValue 