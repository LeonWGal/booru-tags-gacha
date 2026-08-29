import launch

for pkg in ("xmltodict", "aiohttp", "nest_asyncio"):
    if not launch.is_installed(pkg):
        launch.run_pip(f"install {pkg}", f"requests-{pkg}")
