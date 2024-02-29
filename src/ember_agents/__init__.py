import sys
import time
from dotenv import load_dotenv

print("\nInitializing ember_agents package...")

# DEBUG
time.sleep(2)
print("\nNon-zero exit...")
sys.exit(1)

load_dotenv()

print("...ember_agents package initialized")
