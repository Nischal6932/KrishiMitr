#!/usr/bin/env python3
"""
Architecture Diagrams Generator for Smart Farming Assistant
Creates system architecture, data flow, and component diagrams using matplotlib and networkx
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ConnectionPatch
import numpy as np
import networkx as nx
from matplotlib.sankey import Sankey
import seaborn as sns

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")

def create_system_architecture_diagram():
    """Create comprehensive system architecture diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis('off')
    
    # Define colors
    colors = {
        'presentation': '#E3F2FD',  # Light blue
        'application': '#F3E5F5',   # Light purple
        'business': '#E8F5E8',     # Light green
        'ml': '#FFF3E0',           # Light orange
        'external': '#FFEBEE'       # Light red
    }
    
    # Title
    ax.text(5, 11.5, 'Smart Farming Assistant - System Architecture', 
            fontsize=20, fontweight='bold', ha='center')
    
    # Layer 1: Presentation Layer
    pres_box = FancyBboxPatch((0.5, 9), 9, 1.5, 
                              boxstyle="round,pad=0.1", 
                              facecolor=colors['presentation'],
                              edgecolor='black', linewidth=2)
    ax.add_patch(pres_box)
    ax.text(5, 9.75, 'Presentation Layer', fontsize=14, fontweight='bold', ha='center')
    ax.text(5, 9.25, 'HTML/CSS/JS • Web Speech API • Drag & Drop • Real-time Preview', 
            fontsize=10, ha='center')
    
    # Layer 2: Application Layer
    app_box = FancyBboxPatch((0.5, 7), 9, 1.5, 
                             boxstyle="round,pad=0.1", 
                             facecolor=colors['application'],
                             edgecolor='black', linewidth=2)
    ax.add_patch(app_box)
    ax.text(5, 7.75, 'Application Layer', fontsize=14, fontweight='bold', ha='center')
    ax.text(5, 7.25, 'Flask Framework • HTTP Requests • Routing • Session Management', 
            fontsize=10, ha='center')
    
    # Layer 3: Business Logic Layer
    business_box = FancyBboxPatch((0.5, 5), 9, 1.5, 
                                 boxstyle="round,pad=0.1", 
                                 facecolor=colors['business'],
                                 edgecolor='black', linewidth=2)
    ax.add_patch(business_box)
    ax.text(5, 5.75, 'Business Logic Layer', fontsize=14, fontweight='bold', ha='center')
    ax.text(5, 5.25, 'Model Loading • GradCAM • AI Advisory • Caching • Security • Translation', 
            fontsize=10, ha='center')
    
    # Layer 4: Machine Learning Layer
    ml_box = FancyBboxPatch((0.5, 3), 9, 1.5, 
                           boxstyle="round,pad=0.1", 
                           facecolor=colors['ml'],
                           edgecolor='black', linewidth=2)
    ax.add_patch(ml_box)
    ax.text(5, 3.75, 'Machine Learning Layer', fontsize=14, fontweight='bold', ha='center')
    ax.text(5, 3.25, 'ResNet50 CNN • Disease Classification • Ensemble Prediction • Feature Extraction', 
            fontsize=10, ha='center')
    
    # External Services
    external_box = FancyBboxPatch((0.5, 0.5), 9, 1.5, 
                                 boxstyle="round,pad=0.1", 
                                 facecolor=colors['external'],
                                 edgecolor='black', linewidth=2)
    ax.add_patch(external_box)
    ax.text(5, 1.25, 'External Services', fontsize=14, fontweight='bold', ha='center')
    ax.text(5, 0.75, 'Groq API (LLM) • Redis Cache • GitHub Releases • Google Translate', 
            fontsize=10, ha='center')
    
    # Add arrows between layers
    arrows = [(9.75, 7.5), (8.75, 5.5), (7.75, 3.5), (6.75, 1.5)]
    for i, (y1, y2) in enumerate(arrows):
        ax.annotate('', xy=(5, y2), xytext=(5, y1),
                   arrowprops=dict(arrowstyle='->', lw=2, color='black'))
    
    # Add side annotations
    ax.text(0.2, 9.75, 'UI/UX', fontsize=10, rotation=90, va='center')
    ax.text(0.2, 7.75, 'Web', fontsize=10, rotation=90, va='center')
    ax.text(0.2, 5.75, 'Logic', fontsize=10, rotation=90, va='center')
    ax.text(0.2, 3.75, 'AI/ML', fontsize=10, rotation=90, va='center')
    ax.text(0.2, 1.25, 'Cloud', fontsize=10, rotation=90, va='center')
    
    plt.tight_layout()
    plt.savefig('/Users/nischalmittal/Downloads/FINAL-main/extended_project_report/diagrams/system_architecture.png', 
                dpi=300, bbox_inches='tight')
    plt.close()
    print("System architecture diagram created successfully!")

def create_data_flow_diagram():
    """Create data flow pipeline diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(16, 10))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')
    
    # Title
    ax.text(6, 7.5, 'End-to-End Data Flow Pipeline', 
            fontsize=18, fontweight='bold', ha='center')
    
    # Define process boxes
    processes = [
        ('Image Upload', (1, 6), '#FFE0B2'),
        ('Preprocessing', (3, 6), '#E1BEE7'),
        ('Ensemble Prediction', (5, 6), '#C5E1A5'),
        ('GradCAM Generation', (7, 6), '#FFCCBC'),
        ('LLM Advisory', (9, 6), '#B2EBF2'),
        ('Multi-language Output', (11, 6), '#F8BBD9')
    ]
    
    # Draw process boxes
    for name, pos, color in processes:
        box = FancyBboxPatch((pos[0]-0.7, pos[1]-0.4), 1.4, 0.8,
                            boxstyle="round,pad=0.05",
                            facecolor=color, edgecolor='black', linewidth=1.5)
        ax.add_patch(box)
        ax.text(pos[0], pos[1], name, fontsize=10, ha='center', va='center', fontweight='bold')
    
    # Draw arrows
    for i in range(len(processes)-1):
        x1, y1 = processes[i][1]
        x2, y2 = processes[i+1][1]
        ax.annotate('', xy=(x2-0.7, y2), xytext=(x1+0.7, y1),
                   arrowprops=dict(arrowstyle='->', lw=2, color='blue'))
    
    # Add data annotations
    data_flows = [
        ('Leaf Image\n(224x224x3)', (2, 5.2)),
        ('Augmented\nVariants', (4, 5.2)),
        ('Probability\nDistribution', (6, 5.2)),
        ('Attention\nHeatmap', (8, 5.2)),
        ('Treatment\nAdvice', (10, 5.2))
    ]
    
    for text, pos in data_flows:
        ax.text(pos[0], pos[1], text, fontsize=9, ha='center', 
                style='italic', color='darkblue')
    
    # Add side annotations for TTA
    tta_box = FancyBboxPatch((4.3, 3.5), 1.4, 1.2,
                             boxstyle="round,pad=0.05",
                             facecolor='#E8F5E8', edgecolor='green', linewidth=1.5)
    ax.add_patch(tta_box)
    ax.text(5, 4.1, 'TTA\nEnsemble', fontsize=9, ha='center', va='center', fontweight='bold')
    ax.text(5, 3.7, 'Original\nContrast\nBrightness\nSharpened', fontsize=8, ha='center')
    
    # Connect TTA to main flow
    ax.annotate('', xy=(5, 5.6), xytext=(5, 4.7),
               arrowprops=dict(arrowstyle='<->', lw=1.5, color='green', linestyle='--'))
    
    plt.tight_layout()
    plt.savefig('/Users/nischalmittal/Downloads/FINAL-main/extended_project_report/flowcharts/data_flow_pipeline.png', 
                dpi=300, bbox_inches='tight')
    plt.close()
    print("Data flow diagram created successfully!")

def create_model_architecture_diagram():
    """Create detailed CNN model architecture diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis('off')
    
    # Title
    ax.text(5, 11.5, 'ResNet50-based CNN Architecture', 
            fontsize=18, fontweight='bold', ha='center')
    
    # Input layer
    input_box = FancyBboxPatch((4, 10), 2, 0.8,
                              boxstyle="round,pad=0.05",
                              facecolor='#E3F2FD', edgecolor='blue', linewidth=2)
    ax.add_patch(input_box)
    ax.text(5, 10.4, 'Input\n224×224×3', fontsize=11, ha='center', va='center', fontweight='bold')
    
    # ResNet50 Backbone (simplified representation)
    backbone_layers = [
        ('Conv1\n7×7, 64', (5, 9)),
        ('ResBlock1\n3×3, 64', (5, 8)),
        ('ResBlock2\n3×3, 128', (5, 7)),
        ('ResBlock3\n3×3, 256', (5, 6)),
        ('ResBlock4\n3×3, 512', (5, 5))
    ]
    
    for name, pos in backbone_layers:
        box = FancyBboxPatch((pos[0]-0.8, pos[1]-0.3), 1.6, 0.6,
                            boxstyle="round,pad=0.05",
                            facecolor='#F3E5F5', edgecolor='purple', linewidth=1)
        ax.add_patch(box)
        ax.text(pos[0], pos[1], name, fontsize=9, ha='center', va='center')
    
    # Global Average Pooling
    gap_box = FancyBboxPatch((4, 4.2), 2, 0.6,
                             boxstyle="round,pad=0.05",
                             facecolor='#E8F5E8', edgecolor='green', linewidth=1.5)
    ax.add_patch(gap_box)
    ax.text(5, 4.5, 'Global Avg Pool\n2048 features', fontsize=10, ha='center', va='center', fontweight='bold')
    
    # Custom Classification Head
    head_layers = [
        ('Dense\n512 + ReLU\n+ BatchNorm\n+ Dropout(0.5)', (5, 3.2)),
        ('Dense\n256 + ReLU\n+ BatchNorm\n+ Dropout(0.3)', (5, 2.2)),
        ('Output\n15 + Softmax\n+ L2 Reg(0.001)', (5, 1.2))
    ]
    
    for name, pos in head_layers:
        box = FancyBboxPatch((pos[0]-1, pos[1]-0.4), 2, 0.8,
                            boxstyle="round,pad=0.05",
                            facecolor='#FFF3E0', edgecolor='orange', linewidth=1.5)
        ax.add_patch(box)
        ax.text(pos[0], pos[1], name, fontsize=9, ha='center', va='center')
    
    # Output
    output_box = FancyBboxPatch((4, 0.2), 2, 0.6,
                               boxstyle="round,pad=0.05",
                               facecolor='#FFEBEE', edgecolor='red', linewidth=2)
    ax.add_patch(output_box)
    ax.text(5, 0.5, 'Disease\nProbabilities', fontsize=11, ha='center', va='center', fontweight='bold')
    
    # Add connections
    connections = [(10, 9), (9, 8), (8, 7), (7, 6), (6, 4.5), (4.5, 3.2), (3.2, 2.2), (2.2, 1.2), (1.2, 0.5)]
    for y1, y2 in connections:
        ax.annotate('', xy=(5, y2-0.3), xytext=(5, y1+0.3),
                   arrowprops=dict(arrowstyle='->', lw=2, color='black'))
    
    # Add side annotations
    ax.text(8, 7.5, 'Frozen Layers\n(1-100)', fontsize=10, style='italic', color='blue')
    ax.text(8, 6.5, 'Fine-tuned\nLayers (101-175)', fontsize=10, style='italic', color='red')
    
    # Add loss function annotation
    loss_box = FancyBboxPatch((7.5, 1.5), 2, 0.8,
                              boxstyle="round,pad=0.05",
                              facecolor='#F0F0F0', edgecolor='gray', linewidth=1)
    ax.add_patch(loss_box)
    ax.text(8.5, 1.9, 'Focal Loss\nγ=2.0, α=0.25', fontsize=9, ha='center', va='center')
    
    plt.tight_layout()
    plt.savefig('/Users/nischalmittal/Downloads/FINAL-main/extended_project_report/diagrams/model_architecture.png', 
                dpi=300, bbox_inches='tight')
    plt.close()
    print("Model architecture diagram created successfully!")

def create_security_architecture_diagram():
    """Create security architecture diagram"""
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.axis('off')
    
    # Title
    ax.text(5, 7.5, 'Defense-in-Depth Security Architecture', 
            fontsize=16, fontweight='bold', ha='center')
    
    # Security layers
    security_layers = [
        ('Network Security\nHTTPS/TLS • CORS • DDoS Protection', (5, 6), '#E3F2FD'),
        ('Application Security\nInput Validation • SQL Injection Protection', (5, 4.5), '#F3E5F5'),
        ('Data Security\nAES-256 • Key Management • Audit Logging', (5, 3), '#E8F5E8'),
        ('Model Security\nInput Preprocessing • Confidence Thresholding', (5, 1.5), '#FFF3E0')
    ]
    
    for name, pos, color in security_layers:
        box = FancyBboxPatch((pos[0]-2, pos[1]-0.4), 4, 0.8,
                            boxstyle="round,pad=0.1",
                            facecolor=color, edgecolor='black', linewidth=1.5)
        ax.add_patch(box)
        ax.text(pos[0], pos[1], name, fontsize=10, ha='center', va='center')
    
    # Add threat indicators
    threats = [
        ('External Threats', (1, 6), 'red'),
        ('API Abuse', (1, 4.5), 'orange'),
        ('Data Breach', (1, 3), 'darkred'),
        ('Adversarial Examples', (1, 1.5), 'purple')
    ]
    
    for threat, pos, color in threats:
        ax.text(pos[0], pos[1], threat, fontsize=9, color=color, fontweight='bold', ha='center')
        ax.annotate('', xy=(3, pos[1]), xytext=(pos[0]+0.8, pos[1]),
                   arrowprops=dict(arrowstyle='->', lw=1.5, color=color))
    
    plt.tight_layout()
    plt.savefig('/Users/nischalmittal/Downloads/FINAL-main/extended_project_report/diagrams/security_architecture.png', 
                dpi=300, bbox_inches='tight')
    plt.close()
    print("Security architecture diagram created successfully!")

if __name__ == "__main__":
    print("Generating architecture diagrams...")
    create_system_architecture_diagram()
    create_data_flow_diagram()
    create_model_architecture_diagram()
    create_security_architecture_diagram()
    print("All architecture diagrams generated successfully!")
