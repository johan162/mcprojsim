# Design Ideas

This directory is a lightweight workspace for design ideas across **mcprojsim**: both project-level concepts and supporting infrastructure ideas.

### Build PDF Documents

From this directory, run:

```bash
make
```

This builds PDF versions of the design markdown documents and stores them in `dist/` using versioned filenames.

### Clean up temporary build artifacts

```bash
make clean
```

### Remove all built files including generated PDFs

```bash
make really-clean
```

> [!NOTE]
> All PDFs are generated through the shared LaTeX template: `design_template.tex`.
