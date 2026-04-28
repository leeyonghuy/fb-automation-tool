@echo off
chcp 65001 >nul
echo ============================================
echo   KIEM TRA CUDA VA CHAY WHISPER GPU
echo ============================================
echo.

python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'); print('Version:', torch.__version__)"

echo.
echo Neu CUDA: True thi chay dich long tieng...
echo.

python "D:\Contenfactory\DICH_LONG_TIENG.py"

pause
