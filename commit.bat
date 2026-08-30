@echo off
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" add -A
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" commit -m "refactor: improve layout, clean typography and remove excessive emojis"
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" push origin main
pause
