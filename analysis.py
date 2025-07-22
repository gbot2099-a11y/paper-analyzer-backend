from flask import Blueprint, request, jsonify
import openai
import os
from datetime import datetime
import uuid

analysis_bp = Blueprint('analysis', __name__)

# Initialize OpenAI client
client = openai.OpenAI()

@analysis_bp.route('/analyze', methods=['POST'])
def analyze_document():
    """Analyze document for grammar and spelling mistakes"""
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
        
        text = data['text']
        analysis_type = data.get('analysis_type', 'grammar_spelling')
        language = data.get('language', 'english')
        
        # Create analysis prompt based on type
        if analysis_type == 'grammar_only':
            prompt = f"""
            Analyze the following text for GRAMMAR mistakes only. Ignore spelling errors.
            Language: {language}
            
            For each grammar mistake found:
            1. Identify the exact word or phrase with the mistake
            2. Explain what type of grammar error it is
            3. Provide the correct version
            4. Give the position (approximate line/sentence number)
            
            Text to analyze:
            {text}
            
            Return the response in JSON format with this structure:
            {{
                "mistakes": [
                    {{
                        "type": "grammar",
                        "original": "incorrect text",
                        "corrected": "correct text",
                        "explanation": "explanation of the error",
                        "position": "line/sentence number"
                    }}
                ],
                "total_mistakes": number,
                "analysis_type": "grammar_only"
            }}
            """
        elif analysis_type == 'spelling_only':
            prompt = f"""
            Analyze the following text for SPELLING mistakes only. Ignore grammar errors.
            Language: {language}
            
            For each spelling mistake found:
            1. Identify the exact misspelled word
            2. Provide the correct spelling
            3. Give the position (approximate line/sentence number)
            
            Text to analyze:
            {text}
            
            Return the response in JSON format with this structure:
            {{
                "mistakes": [
                    {{
                        "type": "spelling",
                        "original": "misspelled word",
                        "corrected": "correct spelling",
                        "explanation": "spelling correction",
                        "position": "line/sentence number"
                    }}
                ],
                "total_mistakes": number,
                "analysis_type": "spelling_only"
            }}
            """
        else:  # grammar_spelling (default)
            prompt = f"""
            Analyze the following text for both GRAMMAR and SPELLING mistakes.
            Language: {language}
            
            For each mistake found:
            1. Identify the exact word or phrase with the mistake
            2. Specify if it's a grammar or spelling error
            3. Provide the correct version
            4. Explain the error
            5. Give the position (approximate line/sentence number)
            
            Text to analyze:
            {text}
            
            Return the response in JSON format with this structure:
            {{
                "mistakes": [
                    {{
                        "type": "grammar" or "spelling",
                        "original": "incorrect text",
                        "corrected": "correct text",
                        "explanation": "explanation of the error",
                        "position": "line/sentence number"
                    }}
                ],
                "total_mistakes": number,
                "analysis_type": "grammar_spelling"
            }}
            """
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert language teacher and proofreader. Analyze text for mistakes and return results in the exact JSON format requested."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        # Parse the response
        analysis_result = response.choices[0].message.content
        
        # Try to parse as JSON
        try:
            import json
            result = json.loads(analysis_result)
        except json.JSONDecodeError:
            # If JSON parsing fails, create a basic response
            result = {
                "mistakes": [],
                "total_mistakes": 0,
                "analysis_type": analysis_type,
                "raw_response": analysis_result
            }
        
        # Add metadata
        result['analysis_id'] = str(uuid.uuid4())
        result['timestamp'] = datetime.now().isoformat()
        result['language'] = language
        result['text_length'] = len(text)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analysis_bp.route('/upload', methods=['POST'])
def upload_document():
    """Handle document upload and extract text"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file temporarily
        filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join('/tmp', filename)
        file.save(filepath)
        
        # Extract text based on file type
        text = ""
        file_extension = file.filename.lower().split('.')[-1]
        
        if file_extension == 'txt':
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
        elif file_extension == 'pdf':
            # For PDF files, we'll use a simple approach
            # In production, you'd use libraries like PyPDF2 or pdfplumber
            text = "PDF text extraction would be implemented here. For demo purposes, please use text files."
        elif file_extension in ['doc', 'docx']:
            # For Word documents
            text = "Word document text extraction would be implemented here. For demo purposes, please use text files."
        else:
            return jsonify({'error': 'Unsupported file type. Please use .txt, .pdf, or .docx files'}), 400
        
        # Clean up temporary file
        os.remove(filepath)
        
        return jsonify({
            'filename': file.filename,
            'text': text,
            'text_length': len(text),
            'file_type': file_extension
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@analysis_bp.route('/history', methods=['GET'])
def get_analysis_history():
    """Get user's analysis history"""
    # In a real app, this would fetch from database based on user ID
    # For demo purposes, return mock data
    mock_history = [
        {
            'id': '1',
            'filename': 'Essay_Assignment_1.pdf',
            'date': '2 hours ago',
            'mistakes_found': 12,
            'status': 'Completed',
            'analysis_type': 'grammar_spelling',
            'language': 'english'
        },
        {
            'id': '2',
            'filename': 'Research_Paper.docx',
            'date': '1 day ago',
            'mistakes_found': 8,
            'status': 'Completed',
            'analysis_type': 'grammar_only',
            'language': 'english'
        },
        {
            'id': '3',
            'filename': 'Student_Report.pdf',
            'date': '3 days ago',
            'mistakes_found': 15,
            'status': 'Completed',
            'analysis_type': 'spelling_only',
            'language': 'english'
        }
    ]
    
    return jsonify({'history': mock_history})

@analysis_bp.route('/report/<analysis_id>', methods=['GET'])
def get_analysis_report(analysis_id):
    """Get detailed analysis report"""
    # In a real app, this would fetch from database
    # For demo purposes, return mock detailed report
    mock_report = {
        'analysis_id': analysis_id,
        'filename': 'Sample_Document.txt',
        'timestamp': '2025-01-22T10:30:00',
        'analysis_type': 'grammar_spelling',
        'language': 'english',
        'total_mistakes': 5,
        'mistakes': [
            {
                'type': 'grammar',
                'original': 'The students was happy',
                'corrected': 'The students were happy',
                'explanation': 'Subject-verb disagreement. "Students" is plural, so use "were" instead of "was".',
                'position': 'Line 1'
            },
            {
                'type': 'spelling',
                'original': 'recieve',
                'corrected': 'receive',
                'explanation': 'Common spelling error. Remember "i before e except after c".',
                'position': 'Line 3'
            },
            {
                'type': 'grammar',
                'original': 'Me and John went',
                'corrected': 'John and I went',
                'explanation': 'Use "I" instead of "me" when it\'s the subject of the sentence.',
                'position': 'Line 5'
            }
        ],
        'summary': {
            'grammar_mistakes': 3,
            'spelling_mistakes': 2,
            'most_common_error': 'Subject-verb disagreement'
        }
    }
    
    return jsonify(mock_report)

