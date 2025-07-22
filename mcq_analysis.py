from flask import Blueprint, request, jsonify
import openai
import os
from datetime import datetime
import uuid
import json

mcq_bp = Blueprint('mcq_analysis', __name__)

# Initialize OpenAI client
client = openai.OpenAI()

@mcq_bp.route('/upload-answer-key', methods=['POST'])
def upload_answer_key():
    """Upload and process answer key for MCQ analysis"""
    try:
        data = request.get_json()
        
        if not data or 'answer_key' not in data:
            return jsonify({'error': 'Answer key is required'}), 400
        
        answer_key = data['answer_key']
        subject = data.get('subject', 'General')
        total_questions = data.get('total_questions', len(answer_key))
        
        # Validate answer key format
        if not isinstance(answer_key, list):
            return jsonify({'error': 'Answer key must be a list of answers'}), 400
        
        # Process and validate answer key
        processed_key = []
        for i, answer in enumerate(answer_key):
            if isinstance(answer, dict):
                processed_key.append({
                    'question_number': i + 1,
                    'correct_answer': answer.get('answer', '').upper(),
                    'explanation': answer.get('explanation', ''),
                    'marks': answer.get('marks', 1)
                })
            else:
                processed_key.append({
                    'question_number': i + 1,
                    'correct_answer': str(answer).upper(),
                    'explanation': '',
                    'marks': 1
                })
        
        # Generate unique answer key ID
        answer_key_id = str(uuid.uuid4())
        
        # In a real application, you would save this to a database
        # For now, we'll return the processed key with an ID
        
        return jsonify({
            'answer_key_id': answer_key_id,
            'subject': subject,
            'total_questions': len(processed_key),
            'processed_key': processed_key,
            'timestamp': datetime.now().isoformat(),
            'message': 'Answer key uploaded successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@mcq_bp.route('/analyze-mcq-batch', methods=['POST'])
def analyze_mcq_batch():
    """Analyze multiple MCQ answer sheets against an answer key"""
    try:
        data = request.get_json()
        
        if not data or 'answer_key_id' not in data or 'student_answers' not in data:
            return jsonify({'error': 'Answer key ID and student answers are required'}), 400
        
        answer_key_id = data['answer_key_id']
        student_answers = data['student_answers']  # List of student answer sheets
        answer_key = data.get('answer_key', [])  # The correct answers
        
        if not answer_key:
            return jsonify({'error': 'Answer key is required'}), 400
        
        if not isinstance(student_answers, list):
            return jsonify({'error': 'Student answers must be a list'}), 400
        
        # Check subscription limits
        user_plan = data.get('user_plan', 'free')
        max_analyses = get_mcq_limit(user_plan)
        
        if len(student_answers) > max_analyses:
            return jsonify({
                'error': f'Your {user_plan} plan allows maximum {max_analyses} MCQ analyses. You submitted {len(student_answers)}.'
            }), 400
        
        results = []
        
        for idx, student_sheet in enumerate(student_answers):
            try:
                # Analyze individual student sheet
                analysis_result = analyze_single_mcq_sheet(
                    student_sheet, 
                    answer_key, 
                    idx + 1
                )
                results.append(analysis_result)
                
            except Exception as e:
                results.append({
                    'student_id': idx + 1,
                    'error': f'Failed to analyze sheet {idx + 1}: {str(e)}',
                    'score': 0,
                    'total_questions': len(answer_key)
                })
        
        # Generate summary statistics
        summary = generate_batch_summary(results, answer_key)
        
        return jsonify({
            'analysis_id': str(uuid.uuid4()),
            'answer_key_id': answer_key_id,
            'total_sheets_analyzed': len(results),
            'timestamp': datetime.now().isoformat(),
            'summary': summary,
            'individual_results': results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def analyze_single_mcq_sheet(student_answers, answer_key, student_id):
    """Analyze a single student's MCQ answer sheet"""
    correct_answers = 0
    wrong_answers = 0
    unanswered = 0
    mistakes = []
    
    for i, correct_answer in enumerate(answer_key):
        question_num = i + 1
        student_answer = student_answers.get(str(question_num), '').upper() if isinstance(student_answers, dict) else (student_answers[i].upper() if i < len(student_answers) else '')
        correct = correct_answer.get('correct_answer', correct_answer).upper() if isinstance(correct_answer, dict) else str(correct_answer).upper()
        
        if not student_answer or student_answer == '':
            unanswered += 1
            mistakes.append({
                'question_number': question_num,
                'type': 'unanswered',
                'student_answer': '',
                'correct_answer': correct,
                'explanation': f'Question {question_num} was not answered'
            })
        elif student_answer == correct:
            correct_answers += 1
        else:
            wrong_answers += 1
            mistakes.append({
                'question_number': question_num,
                'type': 'incorrect',
                'student_answer': student_answer,
                'correct_answer': correct,
                'explanation': f'Question {question_num}: Selected {student_answer}, correct answer is {correct}'
            })
    
    total_questions = len(answer_key)
    score_percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
    
    return {
        'student_id': student_id,
        'score': correct_answers,
        'total_questions': total_questions,
        'score_percentage': round(score_percentage, 2),
        'correct_answers': correct_answers,
        'wrong_answers': wrong_answers,
        'unanswered': unanswered,
        'mistakes': mistakes,
        'grade': calculate_grade(score_percentage)
    }

def generate_batch_summary(results, answer_key):
    """Generate summary statistics for batch analysis"""
    if not results:
        return {}
    
    total_students = len(results)
    total_questions = len(answer_key)
    
    # Calculate averages
    total_score = sum(result.get('score', 0) for result in results)
    average_score = total_score / total_students if total_students > 0 else 0
    average_percentage = (average_score / total_questions) * 100 if total_questions > 0 else 0
    
    # Grade distribution
    grade_distribution = {}
    for result in results:
        grade = result.get('grade', 'F')
        grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
    
    # Question-wise analysis
    question_analysis = []
    for i in range(total_questions):
        question_num = i + 1
        correct_count = 0
        
        for result in results:
            if result.get('score', 0) > i:  # Simplified check
                correct_count += 1
        
        difficulty = 'Easy' if correct_count / total_students > 0.8 else 'Medium' if correct_count / total_students > 0.5 else 'Hard'
        
        question_analysis.append({
            'question_number': question_num,
            'correct_responses': correct_count,
            'incorrect_responses': total_students - correct_count,
            'success_rate': round((correct_count / total_students) * 100, 2),
            'difficulty': difficulty
        })
    
    return {
        'total_students': total_students,
        'total_questions': total_questions,
        'average_score': round(average_score, 2),
        'average_percentage': round(average_percentage, 2),
        'highest_score': max(result.get('score', 0) for result in results),
        'lowest_score': min(result.get('score', 0) for result in results),
        'grade_distribution': grade_distribution,
        'question_analysis': question_analysis
    }

def calculate_grade(percentage):
    """Calculate letter grade based on percentage"""
    if percentage >= 90:
        return 'A+'
    elif percentage >= 85:
        return 'A'
    elif percentage >= 80:
        return 'A-'
    elif percentage >= 75:
        return 'B+'
    elif percentage >= 70:
        return 'B'
    elif percentage >= 65:
        return 'B-'
    elif percentage >= 60:
        return 'C+'
    elif percentage >= 55:
        return 'C'
    elif percentage >= 50:
        return 'C-'
    elif percentage >= 45:
        return 'D'
    else:
        return 'F'

def get_mcq_limit(plan):
    """Get MCQ analysis limit based on subscription plan"""
    limits = {
        'free': 0,
        'basic': 0,
        'standard': 200,
        'premium': 500
    }
    return limits.get(plan.lower(), 0)

@mcq_bp.route('/mcq-history', methods=['GET'])
def get_mcq_history():
    """Get MCQ analysis history"""
    # In a real app, this would fetch from database based on user ID
    mock_history = [
        {
            'id': '1',
            'answer_key_id': 'key_123',
            'subject': 'Mathematics',
            'date': '2 hours ago',
            'total_students': 25,
            'average_score': 78.5,
            'status': 'Completed'
        },
        {
            'id': '2',
            'answer_key_id': 'key_124',
            'subject': 'Science',
            'date': '1 day ago',
            'total_students': 30,
            'average_score': 82.3,
            'status': 'Completed'
        }
    ]
    
    return jsonify({'history': mock_history})

@mcq_bp.route('/mcq-report/<analysis_id>', methods=['GET'])
def get_mcq_report(analysis_id):
    """Get detailed MCQ analysis report"""
    # In a real app, this would fetch from database
    mock_report = {
        'analysis_id': analysis_id,
        'subject': 'Mathematics Test',
        'timestamp': '2025-01-22T10:30:00',
        'total_students': 25,
        'total_questions': 50,
        'summary': {
            'average_score': 38.5,
            'average_percentage': 77.0,
            'highest_score': 48,
            'lowest_score': 22,
            'grade_distribution': {
                'A+': 3,
                'A': 5,
                'B+': 8,
                'B': 6,
                'C': 2,
                'D': 1
            }
        },
        'question_analysis': [
            {
                'question_number': 1,
                'correct_responses': 23,
                'success_rate': 92.0,
                'difficulty': 'Easy'
            },
            {
                'question_number': 2,
                'correct_responses': 15,
                'success_rate': 60.0,
                'difficulty': 'Medium'
            }
        ]
    }
    
    return jsonify(mock_report)

