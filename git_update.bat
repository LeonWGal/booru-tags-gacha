@echo off
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" add -A
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" commit -m "feat: adaptive UI, Lobe Theme support, universal tag classifier, and updated docs"
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" push origin main
pause
