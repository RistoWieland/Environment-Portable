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


def download_update():
    # Open the repository
    repo = git.Repo(repo_path)

    # Fetch the latest changes from the remote repository
    origin = repo.remotes.origin
    origin.fetch()

    # Pull the latest changes from the remote repository
    repo.git.pull()

    # Get the latest commit hash from the remote repository
    latest_commit_remote = repo.commit('origin/master')

    # Get the latest commit hash from the local repository
    latest_commit_local = repo.commit('master')

    # Check if the latest commit hashes are different
    print("latest commit lcoal : ", latest_commit_local)
    print("latest commit remote : ", latest_commit_remote)
    if latest_commit_remote != latest_commit_local:
        # Check if the script file has changed
        changed_files = [item.a_path for item in repo.index.diff('HEAD')]
        print("changed files : ", changed_files)
        print("script name : ", script_name)
        if script_name in changed_files:
            return True  # Indicates that the script file has been updated
        else:
            return False  # Indicates that no updates are available
    else:
        return False  # Indicates that no updates are available


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
