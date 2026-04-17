# 🌱 Smart Farming Assistant

An AI-powered plant disease detection system using deep learning with real-time image analysis and IoT integration.

## 🚀 Features

- **🔍 Disease Detection**: 79.52% accuracy across 15 plant disease classes
- **📱 Real-time Analysis**: Upload images for instant disease detection
- **🌐 Multi-language Support**: Audio responses in multiple languages
- **📊 IoT Integration**: Soil moisture monitoring and sensor data
- **🎯 GradCAM Visualization**: Explainable AI with heatmaps
- **🔒 Security**: File validation, rate limiting, and secure uploads

## 🧠 Model Information

### **Best Performing Model: v4**
- **Model File**: `plant_disease_realworld_15class_best_v4.keras`
- **Test Accuracy**: **79.52%**
- **Top-3 Accuracy**: **96.03%**
- **Architecture**: MobileNetV3Large
- **Input Size**: 160x160 RGB images
- **Classes**: 15 plant disease categories

### **Supported Classes**
1. Pepper__bell___Bacterial_spot
2. Pepper__bell___healthy
3. Potato___Early_blight
4. Potato___Late_blight
5. Potato___healthy
6. Tomato_Bacterial_spot
7. Tomato_Early_blight
8. Tomato_Late_blight
9. Tomato_Leaf_Mold
10. Tomato_Septoria_leaf_spot
11. Tomato_Spider_mites_Two_spotted_spider_mite
12. Tomato__Target_Spot
13. Tomato__Tomato_YellowLeaf__Curl_Virus
14. Tomato__Tomato_mosaic_virus
15. Tomato_healthy

## 🛠️ Installation

### **Prerequisites**
- Python 3.13+
- TensorFlow 2.16.1+
- Redis (optional, for caching)

### **Setup**
```bash
# Clone repository
git clone <repository-url>
cd FINAL-main

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys and configuration

# Create static directory
mkdir -p static
```

### **Environment Variables**
```bash
# Required
GROQ_API_KEY=your_groq_api_key_here

# Optional
MODEL_PATH=plant_disease_realworld_15class_best_v4.keras
FLASK_DEBUG=False
PORT=10000
ENVIRONMENT=production
```

## 🚀 Running the Application

### **Development**
```bash
python3 app.py
```

### **Production with Docker**
```bash
# Build image
docker build -t smart-farming-assistant .

# Run container
docker run -p 10000:10000 smart-farming-assistant

# Or with docker-compose
docker-compose up
```

## 📊 API Endpoints

### **Main Endpoints**
- `GET /` - Main prediction interface
- `POST /predict` - Upload and analyze plant images
- `POST /ai_advice` - Get AI-powered farming advice
- `GET /health` - System health check

### **IoT Endpoints**
- `POST /update_moisture` - Update soil moisture data
- `GET /get_moisture` - Get latest moisture readings
- `GET /iot_status` - IoT device status

## 🔧 Configuration

### **Model Configuration**
The application automatically loads the best available model in this order:
1. `plant_disease_realworld_15class_best_v4.keras` (Primary)
2. `plant_disease_realworld_15class_best.keras` (Fallback)

### **Security Features**
- File type validation (JPG, PNG, WebP)
- File size limit (16MB)
- Rate limiting (10 uploads/minute)
- MIME type verification
- Secure filename handling

## 📈 Performance Metrics

### **Model Performance**
- **Test Accuracy**: 79.52%
- **Validation Accuracy**: 81.20%
- **Top-3 Accuracy**: 96.03%
- **Model Size**: ~25MB
- **Inference Time**: ~200ms per image

### **System Performance**
- **Response Time**: <2 seconds (including preprocessing)
- **Memory Usage**: ~500MB
- **Concurrent Users**: Supports 100+ simultaneous requests

## 🧪 Testing

### **Run Tests**
```bash
# Unit tests
python3 -m pytest tests/

# Model validation
python3 predict.py

# Confidence testing
python3 confidence_test.py
```

## 📝 Development

### **Project Structure**
```
FINAL-main/
├── app.py                          # Main Flask application
├── config.py                       # Configuration management
├── security.py                     # Security utilities
├── error_handler.py                # Error handling
├── cache_service.py                # Redis caching
├── model_config.json               # Model metadata
├── requirements.txt               # Python dependencies
├── Dockerfile                    # Container configuration
├── docker-compose.yml            # Multi-container setup
├── static/                      # Upload directory
├── templates/                   # HTML templates
└── tests/                       # Test suite
```

### **Training Scripts**
- `train_70_percent.py` - Basic training script
- `train_high_accuracy.py` - High-accuracy training
- `train_plantvillage_v2.py` - PlantVillage dataset training
- `train_replacement_model.py` - Model replacement training

## 🚀 Deployment

### **Environment Setup**
1. **Production Environment Variables**
   ```bash
   FLASK_ENV=production
   ENVIRONMENT=production
   SECRET_KEY=your-secure-secret-key
   ```

2. **Model Files**
   - Ensure `plant_disease_realworld_15class_best_v4.keras` is present
   - Or configure automatic download from GitHub releases

3. **Redis (Optional)**
   ```bash
   docker run -d -p 6379:6379 redis:7-alpine
   ```

### **Monitoring**
- Health checks at `/health`
- Application logs via `smart_farming.log`
- Performance metrics available at `/debug` (debug mode only)

## 🔒 Security

### **Implemented Measures**
- Input validation and sanitization
- File type and size restrictions
- Rate limiting per IP
- Secure headers
- Non-root Docker user
- Environment variable protection

### **Best Practices**
- Regular security updates
- API key rotation
- Log monitoring
- Backup strategies

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **PlantVillage Dataset** - Training data source
- **MobileNetV3** - Base architecture
- **Groq** - AI inference services
- **TensorFlow** - Deep learning framework

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check the troubleshooting guide
- Review the API documentation

---

**🌱 Smart Farming Assistant - Empowering farmers with AI-driven disease detection**
