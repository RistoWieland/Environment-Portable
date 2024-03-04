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
import hashlib


# where the config file is located and load it as global variable
global config_file
config_file = '/home/statler/Config/config.ini'


def settings_reading(which_section, which_parameter):
    config = configparser.ConfigParser()
    config.read(config_file)
    reading = config[which_section][which_parameter]
    return reading


# Define the path to your local repository on the Raspberry Pi
repo_path = settings_reading("updates", "repo path")

# Define the path where your Python script is stored on the Raspberry Pi
script_path = settings_reading("updates", "script path")

# Define the file name of your Python script
script_name = settings_reading("updates", "script name")

# Define the name of the systemctl service
service_name = settings_reading("updates", "service name")


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


def take_file_snapshot(file_path):
    # Takes a snapshot of the specified file and returns its hash.
    with open(file_path, 'rb') as f:
        file_content = f.read()
        return hashlib.sha256(file_content).hexdigest()


def check_for_changes():
    # Concatenate script_path and script_name to get the full path of the script file
    full_script_path = os.path.join(script_path, script_name)

    # Take a snapshot of the script file before the update
    before_hash = take_file_snapshot(full_script_path)

    # Perform git pull to get the latest changes
    subprocess.run(['sudo', 'git', 'pull'], cwd=repo_path)

    # Take a snapshot of the script file after the update
    after_hash = take_file_snapshot(full_script_path)

    # Compare the hashes to check if the file has changed
    if before_hash != after_hash:
        return True
    else:
        return False


def restart_service():
    # Restart the systemctl service
    subprocess.run(['sudo', 'systemctl', 'restart', service_name])


while True:
    if check_for_updates():
        print("New version available. Downloading...")
        if check_for_changes():
            print("New script is available. Restarting service...")
            restart_service()
            print("Service restarted.")
        else:
            print("No new script is available. Restarting service skipped")
    print("No updates available.")
    time.sleep(120)
