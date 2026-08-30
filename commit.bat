@echo off
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" add -A
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" commit -m "feat: clean default presets with Character (1girl), Scenery (No Humans), NSFW (Explicit), and Empty"
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" push origin main
pause
