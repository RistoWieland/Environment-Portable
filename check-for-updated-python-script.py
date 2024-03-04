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
    # Get the list of changed files between the local and remote repositories
    repo = git.Repo(repo_path)
    diff_index = repo.index.diff(None)

    # Get the paths of the changed files
    changed_files = [item.a_path for item in diff_index]

    # Download only the changed files
    for file in changed_files:
        remote_file_path = os.path.join(repo_path, file)
        subprocess.run(['sudo', 'git', 'checkout', 'origin/master', '--', file])

    # Check if the script file is among the changed files
    print("downloaded : ", changed_files)
    print("script : ", script_name)
    if os.path.basename(script_name) in [os.path.basename(file) for file in changed_files]:
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
