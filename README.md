# Trainer-Cam Rehabilitation (Source)

A rehab exercise coaching prototype that records human motion, extracts 3D skeleton joints, compares a user's motion to a tutor demo, and visualizes where they differ.

## What is in this repo

### simple_3d_viewer/ (C++ / Azure Kinect Body Tracking / OpenCV)
Records to a folder path (passed as argv[1]) and produces:
- output2.txt — per-frame body skeleton joints (32 joints)
- imamge_idx_<frame>.jpg — RGB frames saved per frame

### TutorClient/ (Qt/C++)
Tutor-side desktop UI:
- creates a new recording folder
- launches the recorder/viewer executable to capture a tutor demo
- can replay a recording (via the showvideo tool when packaged)

### CustomerClient/ (Qt/C++)
Customer-side desktop UI:
- shows a list of customer recordings
- runs the analysis tool against a selected tutor demo + customer session
- opens the analysis viewer window that displays saved combined frames

### test_exe/ (Python)
Core motion-comparison logic lives in 	est_exe/main.py.

It:
1) loads tutor + customer skeletons from output2.txt
2) computes angle features for selected joint-pairs
3) smooths with a Gaussian filter
4) aligns sequences with DTW (warping path)
5) computes per-aligned-frame distances and:
   - prints a score (--function score), or
   - generates an analysis visualization (--function showVideos) that saves images under customer_folder\analyse\

### show_videos/ (Python)
Plays back an image sequence *_idx_*.jpg as a quick video viewer.

## Expected folder layout for a recording session
A recording folder is expected to contain:
- output2.txt
- imamge_idx_0.jpg, imamge_idx_1.jpg, ...

## Notes
- Build outputs, binaries, large dependencies (NuGet packages, OpenCV DLLs, PyInstaller dist/build) are intentionally ignored via .gitignore.
- Recording videos/images can contain sensitive data; do not upload real patient data to public repos.
