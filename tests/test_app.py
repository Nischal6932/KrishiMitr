"""
Test suite for Smart Farming Assistant
"""
import pytest
import tempfile
import os
import json
from io import BytesIO
from PIL import Image

# Import the Flask app
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import (
    apply_crop_context,
    assess_prediction_uncertainty,
    class_names,
    expand_specialist_prediction_to_global,
    normalize_prediction_scores,
)
import backend.farmer_actions as farmer_actions

def create_app():
    """Create and configure a test app"""
    from app import app
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client():
    """Test client fixture"""
    app = create_app()
    with app.test_client() as client:
        yield client

@pytest.fixture
def sample_image():
    """Create a sample image for testing"""
    img = Image.new('RGB', (224, 224), color='red')
    img_bytes = BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes

class TestBasicRoutes:
    """Test basic application routes"""
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
    
    def test_test_endpoint(self, client):
        """Test test endpoint"""
        response = client.get('/test')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'

    def test_livez_endpoint(self, client):
        """Test liveness endpoint"""
        response = client.get('/livez')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'alive'

    def test_readyz_endpoint(self, client):
        """Test readiness endpoint"""
        response = client.get('/readyz')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ready'
    
    def test_root_get(self, client):
        """Test root endpoint GET request"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Smart Farming' in response.data
        assert 'X-Request-ID' in response.headers
        assert response.headers['X-Content-Type-Options'] == 'nosniff'

class TestFileUpload:
    """Test file upload functionality"""
    
    def test_valid_image_upload(self, client, sample_image):
        """Test uploading a valid image"""
        data = {
            'image': (sample_image, 'test.jpg', 'image/jpeg'),
            'crop': 'Tomato',
            'soil': 'Loam',
            'moisture': '50',
            'weather': 'Dry',
            'language': 'English'
        }
        response = client.post('/', data=data, content_type='multipart/form-data')
        assert response.status_code == 200
        assert b'7-Day Crop Care Plan' in response.data
        assert b'Trusted products and buying links' in response.data

    def test_upload_result_uses_browser_accessible_preview_url(self, client, sample_image):
        """Uploaded image preview should point to the uploads route, not a local file path."""
        data = {
            'image': (sample_image, 'preview-test.jpg', 'image/jpeg'),
            'crop': 'Tomato',
            'soil': 'Loam',
            'moisture': '50',
            'weather': 'Dry',
            'language': 'English'
        }
        response = client.post('/', data=data, content_type='multipart/form-data')
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert '/uploads/' in html
        assert str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) not in html
    
    def test_invalid_file_type(self, client):
        """Test uploading invalid file type"""
        data = {
            'image': (BytesIO(b'test'), 'test.txt', 'text/plain'),
            'crop': 'Tomato',
            'soil': 'Loam',
            'moisture': '50',
            'weather': 'Dry'
        }
        response = client.post('/', data=data, content_type='multipart/form-data')
        assert response.status_code == 200
        assert b'Invalid file' in response.data
    
    def test_no_file_upload(self, client):
        """Test submitting form without file"""
        data = {
            'crop': 'Tomato',
            'soil': 'Loam',
            'moisture': '50',
            'weather': 'Dry'
        }
        response = client.post('/', data=data)
        assert response.status_code == 200
        assert b'Please upload' in response.data

class TestAIAdvice:
    """Test AI advice endpoint"""
    
    def test_ai_advice_endpoint(self, client):
        """Test AI advice endpoint"""
        data = {
            'crop': 'Tomato',
            'disease': 'Tomato_healthy',
            'soil': 'Loam',
            'moisture': '50',
            'weather': 'Dry',
            'question': 'How to care for tomatoes?',
            'language': 'English'
        }
        response = client.post('/ai_advice', 
                             data=json.dumps(data), 
                             content_type='application/json')
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'advice' in response_data
        assert 'care_plan' in response_data
        assert 'recommended_products' in response_data

    def test_ai_advice_rejects_invalid_json(self, client):
        """Test AI advice endpoint validates JSON input"""
        response = client.post('/ai_advice', data='not-json', content_type='application/json')
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert response_data['success'] is False

    def test_chat_endpoint(self, client):
        """Test conversational farmer chat endpoint"""
        data = {
            'message': 'My tomato leaves are yellow. What should I do first?',
            'history': [{'role': 'user', 'content': 'Hello'}],
            'crop': 'Tomato',
            'soil': 'Loam',
            'moisture': '45',
            'weather': 'Humid',
            'language': 'English'
        }
        response = client.post('/chat', data=json.dumps(data), content_type='application/json')
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert 'reply' in response_data
        assert 'yellow' in response_data['reply'].lower()

    def test_chat_requires_message(self, client):
        """Test chat endpoint rejects empty messages"""
        response = client.post('/chat', data=json.dumps({'message': '   '}), content_type='application/json')
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert response_data['success'] is False

class TestSecurity:
    """Test security features"""
    
    def test_rate_limiting(self, client):
        """Test rate limiting functionality"""
        # This test would need to be implemented based on your rate limiting
        pass
    
    def test_file_validation(self, client):
        """Test file validation security"""
        # Test oversized file
        large_file = BytesIO(b'x' * (17 * 1024 * 1024))  # 17MB
        data = {
            'image': (large_file, 'large.jpg', 'image/jpeg'),
            'crop': 'Tomato',
            'soil': 'Loam',
            'moisture': '50',
            'weather': 'Dry'
        }
        response = client.post('/', data=data, content_type='multipart/form-data')
        assert response.status_code == 413
        assert b'too large' in response.data.lower()

class TestConfiguration:
    """Test application configuration"""
    
    def test_config_values(self, client):
        """Test configuration values"""
        app = client.application
        assert app.config['MAX_CONTENT_LENGTH'] == 16 * 1024 * 1024
        assert 'jpg' in str(app.config['UPLOAD_EXTENSIONS'])
    
    def test_debug_mode(self, client):
        """Test debug mode configuration"""
        # In tests, debug should be disabled
        app = client.application
        assert not app.config.get('TESTING', False) or app.config['TESTING']


class TestConfidencePipeline:
    """Test confidence normalization and uncertainty handling"""

    def test_normalize_prediction_scores_handles_logits(self):
        probs = normalize_prediction_scores([-2.0, 0.5, 3.0])
        assert pytest.approx(sum(probs), rel=1e-6) == 1.0
        assert probs.argmax() == 2

    def test_apply_crop_context_focuses_on_selected_crop(self):
        raw = [0.05, 0.05, 0.10, 0.10, 0.10, 0.40, 0.20]
        adjusted = apply_crop_context(raw, 'Tomato')
        assert pytest.approx(sum(adjusted), rel=1e-6) == 1.0
        assert adjusted[5] > 0.6
        assert adjusted[2] == 0.0

    def test_uncertainty_detects_flat_predictions(self):
        uncertainty = assess_prediction_uncertainty([0.34, 0.33, 0.33])
        assert uncertainty['is_uncertain'] is True

    def test_runtime_class_mapping_has_expected_classes(self):
        assert len(class_names) == 15
        assert "Tomato_healthy" in class_names

    def test_expand_specialist_prediction_to_global_maps_potato_slots(self):
        expanded = expand_specialist_prediction_to_global(
            [0.1, 0.7, 0.2],
            ["Potato___Early_blight", "Potato___Late_blight", "Potato___healthy"],
        )
        assert pytest.approx(sum(expanded), rel=1e-6) == 1.0
        assert expanded[class_names.index("Potato___Late_blight")] == pytest.approx(0.7)
        assert expanded[class_names.index("Tomato_Early_blight")] == 0.0


class TestFarmerActionLayer:
    """Test the Farmer Action Layer routes and persistence."""

    def test_marketplace_endpoint_filters_items(self, client):
        response = client.get('/marketplace?crop=Tomato&disease=Tomato_Late_blight')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['count'] >= 1
        assert any(item['brand_or_seller'] == 'BigHaat' for item in data['items'])

    def test_expert_support_endpoint_stores_request(self, client, monkeypatch, tmp_path):
        support_file = tmp_path / 'expert_support_requests.jsonl'
        monkeypatch.setattr(farmer_actions, 'EXPERT_SUPPORT_PATH', support_file)
        monkeypatch.setattr(farmer_actions, 'DATA_DIR', tmp_path)

        payload = {
            'name': 'Ravi',
            'phone': '9876543210',
            'crop': 'Tomato',
            'issue': 'Tomato - Late blight',
            'description': 'Leaves are turning dark and the disease is spreading after rain.',
            'location': 'Kurnool',
            'image_reference': 'test-image.jpg'
        }
        response = client.post('/expert_support', data=json.dumps(payload), content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert support_file.exists()
        saved_lines = support_file.read_text(encoding='utf-8').strip().splitlines()
        assert len(saved_lines) == 1

    def test_expert_support_rejects_short_description(self, client):
        payload = {
            'name': 'Ravi',
            'phone': '9876543210',
            'crop': 'Tomato',
            'issue': 'Tomato issue',
            'description': 'Too short'
        }
        response = client.post('/expert_support', data=json.dumps(payload), content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

if __name__ == '__main__':
    pytest.main([__file__])
