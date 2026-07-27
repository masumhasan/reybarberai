# AWS EC2 Deployment Guide (Ubuntu)

This guide walks you through deploying your FastAPI application to an AWS EC2 instance from scratch, ensuring it runs continuously using PM2.

## Prerequisites
- You have provisioned an Ubuntu EC2 instance on AWS.
- You have SSH access to your instance.
- You have opened port `8081` in your EC2 instance's **Security Group** so it can be accessed from the web.

---

## Connecting to Your EC2 Instance

Before setting up the server, configure the permissions of your private key file (`barber.pem`) and connect to your EC2 instance.

### 1. Set Permissions for the Private Key
On your local machine (Linux/macOS, Git Bash, or WSL/PowerShell), restrict the permissions of your private key:
```bash
chmod 400 barber.pem
```

### 2. SSH into the EC2 Instance
Connect to the server using either the public DNS or public IP:

- **Via Public DNS:**
  ```bash
  ssh -i "barber.pem" ubuntu@ec2-13-48-206-147.eu-north-1.compute.amazonaws.com
  ```
- **Via Public IP:**
  ```bash
  ssh -i "barber.pem" ubuntu@13.48.206.147
  ```

---

## 1. System Update
First, update the package list and upgrade existing packages:
```bash
sudo apt update && sudo apt upgrade -y
```

## 2. Install Python, Git, and Virtual Environment
Install Python 3, pip, the python venv module, and Git:
```bash
sudo apt install python3 python3-pip python3-venv git curl -y
```

## 3. Clone Your Repository
Clone your GitHub repository and move into the project folder:
```bash
git clone https://github.com/masumhasan/reybarberai.git
cd reybarberai
```

## 4. Setup the Python Virtual Environment
Create and activate your virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

## 5. Install Python Dependencies
Install all the required Python packages for your app:
```bash
pip install -r requirements.txt
```
*(This may take a few minutes as it downloads large AI libraries like torch.)*

## 6. Install Node.js and PM2
PM2 is a production process manager for Node.js, but it works brilliantly for Python too. It requires Node.js to be installed.

Install Node.js:
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

Install PM2 globally:
```bash
sudo npm install pm2 -g
```

## 7. Start the Application with PM2
Since we added an execution block to `main.py` (which runs Uvicorn on port 8081), we can instruct PM2 to run `main.py` using the Python interpreter from our virtual environment.

Run this command inside the `reybarberai` directory:
```bash
pm2 start main.py --name "reybarberAI-api" --interpreter ./venv/bin/python
```

*(Alternatively, you can run Uvicorn directly via PM2: `pm2 start "./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8081" --name "reybarberAI-api"`)*


## 8. Save PM2 and Setup Auto-Start
To ensure your FastAPI application restarts automatically if the EC2 instance reboots:

1. Generate the startup script:
   ```bash
   pm2 startup
   ```
2. **Important:** The output of the above command will give you a specific `sudo env PATH...` command to run. **Copy and paste that command** into your terminal and press Enter.

3. Finally, save the current PM2 list so it remembers to start your app:
   ```bash
   pm2 save
   ```

---

## Useful PM2 Commands for Maintenance
- Check the status of your app: `pm2 status`
- View live application logs: `pm2 logs reybarberAI-api`
- Restart the app (e.g., after pulling new git updates): `pm2 restart reybarberAI-api`
- Stop the app: `pm2 stop reybarberAI-api`
