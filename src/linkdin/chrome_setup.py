import subprocess
import time
import webbrowser

def open_linkedin_in_active_chrome(job_title, location):
    """
    Open LinkedIn jobs search in the active Chrome window
    
    Args:
        job_title (str): Job title to search for
        location (str): Location to search in
    """
    # Format the search URL
    search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title}&location={location}"
    
    try:
        # Get the active Chrome window
        chrome_window = subprocess.check_output(["xdotool", "search", "--onlyvisible", "--class", "google-chrome"]).strip().split()[0].decode('utf-8')
        
        # Activate the Chrome window
        subprocess.run(["xdotool", "windowactivate", chrome_window])
        
        # Give the window some time to focus
        time.sleep(1)
        
        # Open a new tab with Ctrl+T
        subprocess.run(["xdotool", "key", "--window", chrome_window, "ctrl+t"])
        
        # Give some time for the new tab to open
        time.sleep(1)
        
        # Type the URL and press Enter
        subprocess.run(["xdotool", "type", "--window", chrome_window, search_url])
        subprocess.run(["xdotool", "key", "--window", chrome_window, "Return"])
        
        # Return true to indicate success
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error accessing Chrome window: {e}")
        # If Chrome is not running, open it with the given URL
        webbrowser.open(search_url)
        return False

def check_chrome_debugging_running(port=9222):
    """
    Check if Chrome is already running with debugging on specified port
    """
    try:
        # Find processes with --remote-debugging-port
        result = subprocess.run(
            ["pgrep", "-f", f"--remote-debugging-port={port}"],
            capture_output=True,
            text=True
        )
        return bool(result.stdout.strip())
    except Exception:
        return False

def start_chrome_debugging(port=9222):
    """
    Start a new Chrome instance with debugging enabled
    """
    try:
        # Only try to kill existing debugging session if one exists
        if check_chrome_debugging_running(port):
            try:
                subprocess.run(
                    ["pkill", "-f", f"--remote-debugging-port={port}"], 
                    check=False
                )
                time.sleep(2)
            except Exception as e:
                print(f"Warning: Failed to kill existing debugging session: {e}")
        
        # Start Chrome with debugging enabled
        subprocess.Popen([
            "google-chrome",
            f"--remote-debugging-port={port}",
            "--user-data-dir=/tmp/chrome-debug",
            "--no-first-run"
        ])
        
        # Give Chrome time to start
        time.sleep(5)
        return True
    except Exception as e:
        print(f"Error starting Chrome with debugging: {e}")
        return False