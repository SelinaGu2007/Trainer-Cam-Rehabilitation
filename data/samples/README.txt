This folder is for small, shareable demo inputs (NO private patient data).

Expected format for a session folder (tutor or customer):
- session.json
- frames.jsonl
- output2.txt
- image_idx_0.jpg, image_idx_1.jpg, ... (optional in synthetic samples)

To run:
python test_exe/main.py --folder_tutor data/samples/tutor_session --folder_customer data/samples/customer_session --function score

The committed versioned sessions and legacy compatibility data are synthetic. They contain
no RGB images, personal information, or patient recordings, and are intended for
offline score regression tests only.
