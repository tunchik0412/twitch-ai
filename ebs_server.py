from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import json

app = Flask(__name__)
CORS(app)

# Gemini model
model = None

@app.route('/api/gemini', methods=['POST'])
def gemini_handler():
    data = request.json
    prompt = data.get('prompt', '')
    command = data.get('command', 'ask')
    style = data.get('style', 'friendly')
    
    # Get config from request (passed from extension)
    # In production, you'd fetch from database per channel
    
    style_prompts = {
        'friendly': "You are a friendly, helpful AI assistant in a Twitch stream. Keep responses concise and engaging.",
        'professional': "You are a professional AI assistant. Provide clear, informative responses.",
        'funny': "You are a hilarious AI assistant. Make people laugh with your responses.",
        'lore': "You are an AI from a fantasy world. Respond with RPG-style flavor."
    }
    
    command_prompts = {
        'ask': f"Answer this question: {prompt}",
        'roast': f"Give a playful, light-hearted roast to {prompt}. Keep it fun, not mean.",
        'joke': "Tell a short, funny joke about gaming or streaming.",
        'fact': "Share an interesting, lesser-known fact."
    }
    
    system_prompt = style_prompts.get(style, style_prompts['friendly'])
    user_prompt = command_prompts.get(command, command_prompts['ask'])
    
    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    
    try:
        response = model.generate_content(full_prompt)
        return jsonify({'reply': response.text[:450]})
    except Exception as e:
        return jsonify({'reply': f"Error: {str(e)[:100]}"}), 500

if __name__ == '__main__':
    genai.configure(api_key='YOUR_API_KEY')  # Will be set per channel
    model = genai.GenerativeModel('gemini-pro')
    app.run(port=5000)