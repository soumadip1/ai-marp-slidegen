# Project Structure

This diagram shows the project structure used directly or indirectly by `main.py`.

```mermaid
flowchart LR
    ROOT["marp-generator/"] --> MAIN["main.py"] & ENV[".env"] & CORE["marp_core/"] & ASSETS["assets/"] & PPT["PPT/"]
    CORE --> CORE_FILES["__init__.py<br>config.py"] & SLIDE["slide/"] & IO["io/"] & EXPORT["export/"] & IMAGE["image/"] & UTILS["utils/"] & TEMPLATES["templates/"]
    SLIDE --> SLIDE_FILES["__init__.py<br>generator.py<br>renderer.py"]
    IO --> IO_FILES["__init__.py<br>file.py"]
    EXPORT --> EXPORT_FILES["__init__.py<br>marp.py"]
    IMAGE --> IMAGE_FILES["__init__.py<br>fetcher.py<br>query_generator.py"]
    UTILS --> UTILS_FILES["__init__.py<br>text.py<br>validators.py<br>mermaid.py"]
    TEMPLATES --> TEMPLATE_FILES["__init__.py<br>prompt.md"]
    PPT --> PPT_FILES[".md<br>.pptx"]
    ASSETS --> DIAGRAMS["* topic"]
    DIAGRAMS --> n1["diagrams/"] & TOPIC_FILES["slide_image_.jpg"]
    n1 --> DIAGRAM_FILES["diagram_slide_.png"]

    n1@{ shape: rect}
     ROOT:::root
     MAIN:::file
     ENV:::file
     CORE:::folder
     ASSETS:::folder
     PPT:::folder
     CORE_FILES:::file
     SLIDE:::folder
     IO:::folder
     EXPORT:::folder
     IMAGE:::folder
     UTILS:::folder
     TEMPLATES:::folder
     SLIDE_FILES:::file
     IO_FILES:::file
     EXPORT_FILES:::file
     IMAGE_FILES:::file
     UTILS_FILES:::file
     TEMPLATE_FILES:::file
     PPT_FILES:::generated
     DIAGRAMS:::folder
     n1:::folder
     TOPIC_FILES:::generated
     DIAGRAM_FILES:::generated
    classDef root fill:#1f4e79,stroke:#14324b,color:#ffffff,stroke-width:2px
    classDef folder fill:#dbeafe,stroke:#3b82f6,color:#16324f,stroke-width:1.5px
    classDef file fill:#ecfdf5,stroke:#22c55e,color:#14532d,stroke-width:1.5px
    classDef generated fill:#fff7ed,stroke:#f59e0b,color:#7c2d12,stroke-width:1.5px
```
