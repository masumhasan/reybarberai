@echo off
echo Initializing Git repository...
git init

echo Adding files...
git add .

echo Committing...
git commit -m "Initial commit or updates"

echo Setting branch to main...
git branch -M main

echo Adding remote repository...
git remote remove origin 2>nul
git remote add origin https://github.com/masumhasan/reybarberai.git

echo Pushing to GitHub...
git push -u origin main --force

echo Done!
pause
