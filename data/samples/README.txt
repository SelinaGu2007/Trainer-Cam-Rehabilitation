This folder is for small, shareable demo inputs (NO private patient data).

Expected format for a session folder (tutor or customer):
- output2.txt
- imamge_idx_0.jpg, imamge_idx_1.jpg, ...

To run:
python test_exe/main.py --folder_tutor data/samples/tutor_session --folder_customer data/samples/customer_session --function score

The committed tutor_session and customer_session data are synthetic. They contain
no RGB images, personal information, or patient recordings, and are intended for
offline score regression tests only.
