# requirements
# sudo pip3 install gitpython
# sudo apt install python3-git
# sudo chown -R root:root /home/kermit/Environment-Portable/
# git config --global --add safe.directory '/home/kermit/Environment-Portable'

import subprocess
import git
import os
import time
import configparser

# Define the path to your local repository on the Raspberry Pi
repo_path = '/home/statler/Environment-Portable/'

# Define the path where your Python script is stored on the Raspberry Pi
script_path = '/home/statler/'

# Define the file name of your Python script
script_name = 'your_script.py'

# Define the name of the systemctl service
service_name = 'your_service_name.service'

def settings_reading(which_section, which_parameter):
    config = configparser.ConfigParser()
    config.read(config_file)
    reading = config[which_section][which_parameter]
    return reading

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

    # Check if the downloaded files include the script_name
    downloaded_files = os.listdir(repo_path)
    print("downloaded : ", download_update)
    print("script : ", script_name)
    if script_name in downloaded_files:
        return True
    else:
        return False

def restart_service():
    # Restart the systemctl service
    subprocess.run(['sudo', 'systemctl', 'restart', service_name])

while True:
    if check_for_updates():
        print("New version available. Downloading...")
        if download_update():
            print("Update downloaded successfully.")
            print("Restarting service...")
            restart_service()
            print("Service restarted.")
        else:
            print("Script file not found after download. Skipping service restart.")
    else:
        print("No updates available.")
    time.sleep(120)
