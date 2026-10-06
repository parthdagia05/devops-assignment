# Linux Homework: My Notes

## Links

A **soft link** stores the path of another file.

```bash
ln -s data.txt soft.txt
```

A **hard link** is another name for the same inode.

```bash
ln data.txt hard.txt
```

If the original is deleted, the hard link still works but the soft link breaks. Soft links can cross filesystems and point to directories, hard links cannot.

---

## Creating users

`useradd` is the basic low level command. It does not create a home folder unless told to.

`adduser` is the Ubuntu helper script. It creates the home folder, copies the default files and asks for a password.

On Ubuntu I would use **adduser**.

```bash
sudo adduser newuser
```

---

## Logs with journalctl

All logs from systemd:

```bash
journalctl
```

Last 20 lines:

```bash
journalctl -n 20
```

Logs of one service:

```bash
journalctl -u ssh
```

Only errors:

```bash
journalctl -p err
```

---

## Commands I use most

| Command | Use |
| --- | --- |
| `pwd` | Print current folder |
| `ls` | List files |
| `cd` | Change folder |
| `mkdir` | Make a folder |
| `touch` | Make an empty file |
| `cp` | Copy |
| `mv` | Move or rename |
| `rm` | Delete |
| `cat` | Show file content |
| `grep` | Search text |
| `find` | Search files |
| `chmod` | Change permissions |
| `ps` | List processes |
| `top` | Live process view |
| `df` | Disk space |
| `du` | Folder size |
| `systemctl` | Manage services |
| `journalctl` | Read logs |

## Summary

These notes cover links, user creation, reading logs with journalctl and the commands I use every day on Linux.
