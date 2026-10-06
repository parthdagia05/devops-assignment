#!/bin/bash
# sysinfo.sh - prints basic system details and saves the process list to a file

# variables
today=$(date)
machine=$(hostname)
me=$(whoami)
out_dir="system_report"
out_file="$out_dir/processes.txt"

echo "---------- System Details ----------"
echo "Date      : $today"
echo "Hostname  : $machine"
echo "User      : $me"

echo
echo "---------- Disk Usage ----------"
df -h

echo
echo "---------- Running Processes ----------"
ps

# reading input from the user
echo
read -p "Enter your name: " student_name
read -p "Enter your roll number: " roll
read -p "Write a short comment: " note

echo "Name        : $student_name"
echo "Roll number : $roll"
echo "Comment     : $note"

# make a folder and an empty file inside it
mkdir -p "$out_dir"
touch "$out_file"

# save the process list into the file with > (overwrites old content)
ps > "$out_file"

echo
echo "Folder '$out_dir' is ready"
echo "Process list written to '$out_file'"
