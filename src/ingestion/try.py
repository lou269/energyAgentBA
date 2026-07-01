import logging

from src.ingestion.loader import download_and_convert_ukdale

def main():
    logging.basicConfig(level=logging.INFO)
    download_and_convert_ukdale()
    
if __name__ == "__main__":
    main()
