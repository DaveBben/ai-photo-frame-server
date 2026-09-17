# Names vulture reports as unused that the frameworks call by reflection.
# FastAPI registers routes by decorator, uvicorn loads create_app by string,
# pydantic-settings reads model_config. Not Python to run: ruff excludes this file.
health_check  # unused function (src/local_shazam/api/routes.py:27)
upload_image  # unused function (src/local_shazam/api/routes.py:33)
transform_image_endpoint  # unused function (src/local_shazam/api/routes.py:91)
get_aesthetic  # unused function (src/local_shazam/api/routes.py:132)
model_config  # unused variable (src/local_shazam/config.py:17)
create_app  # unused function (src/local_shazam/server.py:54)
edit_image  # unused function (src/local_shazam/flux_server.py:66)
