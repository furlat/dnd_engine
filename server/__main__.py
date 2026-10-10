"""python -m server --config private-server.json"""
import argparse
from pathlib import Path
import secrets

import uvicorn

from server.app import create_app
from server.config import SeatCredential, ServerConfig


def main() -> None:
    parser = argparse.ArgumentParser(description='Headless player API server')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8790)
    args = parser.parse_args()
    if args.config is not None:
        config = ServerConfig.model_validate_json(args.config.read_bytes())
    else:
        credential = SeatCredential(seat_id='Expedition', token=secrets.token_urlsafe(32))
        config = ServerConfig(credentials=(credential,))
        print(f'Local Expedition credential: {credential.token}', flush=True)
    uvicorn.run(create_app(config), host=args.host, port=args.port, workers=1)


if __name__ == '__main__':
    main()
