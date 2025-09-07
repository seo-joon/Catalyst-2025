# CISSA: Catalyst
Computing and Information Systems Students Association (CISSA) represents the technology and IT student community at the University of Melbourne, bridging the divide between university and industry by holding various social, industry and networking events. Catalyst is CISSA's annual semester 2 hackathon event. This year, the tracks included "Double Major", "Freedom of Movement" and "Anti-Establishment". 

# benkyou.
"benkyou" means STUDY in Japanese. The name was inspired from "Anki" (jp: Memorisation), another popular platform students commonly use to study, and one that we will be integrating with later on down the line. Our team choose the "__Double Major__" track. This year, we created a website that helps students in other courses, eg. B.Commerce and B.Arts better study and understand the materials they are taught in their coursework. We do this by taking in news from various sources, then categorising based on predefined keywords into topics such as "Mergers and Acquisitions", "Game Theory", "Inflation" etc. Students then have the option of exporting results they've collected into an Anki compatible format (Heading, Concepts) to recognise quicker what topics are covered in each news headline (_Commerce example_). This compilation of up to date news also forms a well categorised database that students can also use when searching for articles.

# Features
_Included with this project are the following features:_
- Basic login and user authentication
- User preferences when onboarding
- News age, concepts and subject filter
- Export Anki compatible format 

# Getting started 
Package installation:
- pip install fastapi uvicorn feedparser python-dateutil python-multipart itsdangerous

Local testing:
- uvicorn main:app --reload --port 8000

Website URL:
- https://catalyst-2025.vercel.app/

Logins:
- admin:terry (for existing user)
- newuser:{any text} (for new user)

# Frameworks
- Tailwind CSS
- FastAPI

# Libraries
- feedparser
- python-dateutil
- python-multipart
- itsdangerous
- uvicorn (local testing)
