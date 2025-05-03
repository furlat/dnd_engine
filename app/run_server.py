import uvicorn
import sys
import os

# Add the parent directory to sys.path to allow importing from dnd package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    print("Starting DnD Engine API server...")
    print("API Documentation available at:")
    print("  - Swagger UI: http://localhost:8000/docs")
    print("  - ReDoc: http://localhost:8000/redoc")
    print("\nPress Ctrl+C to stop the server")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, app_dir=os.path.dirname(os.path.abspath(__file__))) 