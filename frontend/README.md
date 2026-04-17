# Frontend

Modern frontend for Smart Farming Assistant.

## Structure

```
frontend/
├── public/              # Static assets served by Flask
│   ├── assets/          # CSS, fonts, icons
│   │   └── style.css    # Main stylesheet
│   └── uploads/         # User uploaded images
├── templates/           # HTML templates (Jinja2)
│   └── index.html       # Main application page
├── src/                 # Source code (for future React/Vue migration)
│   ├── components/      # UI components
│   ├── pages/           # Page components
│   └── services/        # API services
└── build/               # Production build output
```

## Current Setup

- **Templates**: Flask renders Jinja2 templates from `templates/`
- **Static Files**: CSS and assets served from `public/assets/`
- **Uploads**: User images saved to `public/uploads/`

## Future Migration Path

To convert to React:

1. Move `templates/index.html` logic to `src/App.js`
2. Create React components in `src/components/`
3. Build with `npm run build` → outputs to `build/`
4. Update Flask to serve `build/` instead of `templates/`

## Running

Flask automatically serves from this folder:
```python
app = Flask(__name__,
            template_folder='../frontend/templates',
            static_folder='../frontend/public')
```

Access at: http://localhost:10000
