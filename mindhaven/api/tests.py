from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.core.files.base import ContentFile
import base64
import logging

logger = logging.getLogger(__name__)

class CourseCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info(f"Received request from user: {request.user}")
        logger.info(f"Request data: {request.data}")
        logger.info(f"Request FILES: {request.FILES}")  # Debug: Print all files in the request

        course_data = request.data.copy()
        
        # Extract lessons data
        lessons_data = []
        for key, value in request.data.items():
            if key.startswith('lessons[') and key.endswith(']'):
                index = int(key.split('[')[1].split(']')[0])
                field = key.split(']')[1][1:]
                if len(lessons_data) <= index:
                    lessons_data.append({})
                lessons_data[index][field] = value
        
        logger.info(f"Extracted lessons data: {lessons_data}")  # Debug: Print extracted lessons data

        # Remove lessons data from course_data
        for key in list(course_data.keys()):
            if key.startswith('lessons['):
                del course_data[key]

        # Handle course thumbnail
        if 'thumbnail_file' in request.FILES:
            course_data['thumbnail'] = request.FILES['thumbnail_file']
        elif 'thumbnail' in course_data:
            course_data['thumbnail'] = course_data['thumbnail']

        course_serializer = CourseSerializer(data=course_data)
        if course_serializer.is_valid():
            course = course_serializer.save(user=request.user)
            for lesson_data in lessons_data:
                lesson_data['course'] = course.id
               
                # Handle lesson thumbnail
                lesson_thumbnail_key = f"lessons[{lessons_data.index(lesson_data)}][thumbnail_file]"
                logger.info(f"Looking for lesson thumbnail with key: {lesson_thumbnail_key}")  # Debug
                if lesson_thumbnail_key in request.FILES:
                    lesson_data['thumbnail'] = request.FILES[lesson_thumbnail_key]
                    logger.info(f"Found thumbnail file for lesson: {lesson_data['thumbnail']}")  # Debug
                elif 'thumbnail' in lesson_data and lesson_data['thumbnail'].startswith('data:image'):
                    format, imgstr = lesson_data['thumbnail'].split(';base64,')
                    ext = format.split('/')[-1]
                    lesson_data['thumbnail'] = ContentFile(base64.b64decode(imgstr), name=f'lesson_thumbnail_{lessons_data.index(lesson_data)}.{ext}')
                    logger.info(f"Created thumbnail from base64 for lesson: {lesson_data['thumbnail']}")  # Debug
                else:
                    lesson_data['thumbnail'] = None
                    logger.warning(f"No thumbnail found for lesson at index {lessons_data.index(lesson_data)}")  # Debug
                
                # Handle lesson video
                lesson_video_key = f"lessons[{lessons_data.index(lesson_data)}][video_file]"
                logger.info(f"Looking for lesson video with key: {lesson_video_key}")  # Debug
                if lesson_video_key in request.FILES:
                    lesson_data['video'] = request.FILES[lesson_video_key]
                    logger.info(f"Found video file for lesson: {lesson_data['video']}")  # Debug
                elif 'video' in lesson_data and isinstance(lesson_data['video'], str):
                    logger.warning(f"Video for lesson at index {lessons_data.index(lesson_data)} is a string: {lesson_data['video']}")  # Debug
                    lesson_data['video'] = None
                else:
                    lesson_data['video'] = None
                    logger.warning(f"No video found for lesson at index {lessons_data.index(lesson_data)}")  # Debug
                
                logger.info(f"Lesson data before serialization: {lesson_data}")  # Debug
                lesson_serializer = LessonSerializer(data=lesson_data)
                if lesson_serializer.is_valid():
                    lesson = lesson_serializer.save()
                    logger.info(f"Lesson saved. ID: {lesson.id}, Thumbnail: {lesson.thumbnail}, Video: {lesson.video}")  # Debug
                else:
                    logger.error(f"Lesson serializer errors: {lesson_serializer.errors}")
                    course.delete()
                    return Response(lesson_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            return Response(course_serializer.data, status=status.HTTP_201_CREATED)
        
        logger.error(f"Course serializer errors: {course_serializer.errors}")
        return Response(course_serializer.errors, status=status.HTTP_400_BAD_REQUEST)