@echo off
echo === GIT STATUS BEFORE === > "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha\git_log.txt"
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" status >> "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha\git_log.txt" 2>&1

echo === GIT ADD === >> "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha\git_log.txt"
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" add -A >> "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha\git_log.txt" 2>&1

echo === GIT COMMIT === >> "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha\git_log.txt"
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" commit -m "feat: adaptive UI, Lobe Theme compatibility, universal tag classifier, and clean chips inspector" >> "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha\git_log.txt" 2>&1

echo === GIT PUSH === >> "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha\git_log.txt"
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha" push origin main >> "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha\git_log.txt" 2>&1

echo === ALL DONE === >> "t:\StabilityMatrix\Packages\ForgeNeo\extensions\booru-tags-gacha\git_log.txt"
