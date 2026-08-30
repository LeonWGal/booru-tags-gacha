@echo off
if exist "test_apis.py" del "test_apis.py"
if exist "test_gelbooru.py" del "test_gelbooru.py"
if exist "test_output.txt" del "test_output.txt"
if exist "test_result.txt" del "test_result.txt"
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" add -A
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" commit -m "fix: resolve Danbooru 2-tag limit for anonymous users and fix Rule34 count extraction"
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" push origin main
pause
