"""
Command-line interface for the legacy audio streaming daemon.
"""

import argparse
import sys
from core.processor import AudioChunkProcessor
from core.auth import verify_access_token


def main():
    parser = argparse.ArgumentParser(description="Legacy Audio Stream Processor")
    parser.add_argument("--source", type=str, required=True, help="Path to input audio stream or file")
    parser.add_argument("--token", type=str, required=False, help="Access token for dispatch")
    parser.add_argument("--rate", type=int, default=16000, help="Sampling frequency (Hz)")
    args = parser.parse_args()

    if args.token and not verify_access_token(args.token):
        print("Authentication failure: Invalid or expired access token.", file=sys.stderr)
        sys.exit(1)

    print(f"Initializing stream processor for {args.source} at {args.rate}Hz...")
    processor = AudioChunkProcessor(sample_rate=args.rate)
    processor.start()


if __name__ == "__main__":
    main()
