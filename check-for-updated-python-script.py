# requirements
# sudo pip3 install gitpython

import subprocess
import git
import os
import shutil
import time

# Define the path to your local repository
repo_path = '/home/kermit/Environment-Portable/'

# Define the path where your Python script is stored on the Raspberry Pi
script_path = '/home/kermit/Environment-Portable/'

# Define the name of the Python script to be updated
script_name = 'temperature-display.py'

# Define the name of the systemctl service
service_name = 'temperature-display.service'

def check_for_updates():
    # Open the repository
    repo = git.Repo(repo_path)

    # Fetch the latest changes from the remote repository
    origin = repo.remotes.origin
    origin.fetch()

    # Get the latest commit hash from the remote repository
    latest_commit_remote = repo.commit('origin/master')

    # Get the latest commit hash from the local repository
    latest_commit_local = repo.commit('master')

    # Compare the latest commit hashes
    if latest_commit_remote != latest_commit_local:
        return True
    else:
        return False

def download_update():
    # Pull the latest changes from the remote repository
    repo = git.Repo(repo_path)
    repo.git.pull()

    # Copy the updated script to the specified location
    source_file = os.path.join(repo_path, script_name)
    destination_file = os.path.join(script_path, script_name)
    shutil.copy2(source_file, destination_file)

def restart_service():
    # Restart the systemctl service
    subprocess.run(['sudo', 'systemctl', 'restart', service_name])

while True:
    if check_for_updates():
        print("New version available. Downloading...")
        download_update()
        print("Update downloaded successfully.")
        print("Restarting service...")
        restart_service()
        print("Service restarted.")
    else:
        print("No updates available.")
    time.sleep(120)
