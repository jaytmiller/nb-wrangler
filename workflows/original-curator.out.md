flowchart LR
    Curator[Laptop] -->|defines YAML spec| nb-curator_tool[Tool];
    nb-curator_tool -->|downloads notebooks & requirements| GitHub[notebook repositories];
    GitHub -->|notebooks & requirements| nb-curator_tool;
    nb-curator_tool -->|creates environment| conda-forge[conda-forge];
    nb-curator_tool -->|creates environment| pypi[pypi];
    conda-forge -->|packages| nb-curator_tool;
    pypi -->|packages| nb-curator_tool;
    nb-curator_tool -->|runs notebooks & tests| Papermill[Papermill];
    Papermill -->|test results| nb-curator_tool;
    nb-curator_tool -->|builds Docker image| science-platform-images[science-platform-images GitHub repo];
    science-platform-images -->|Docker image| AWS_ECR[AWS ECR];
    AWS_ECR -->|Docker image| JupyterHubs[Science Platform JupyterHubs];

