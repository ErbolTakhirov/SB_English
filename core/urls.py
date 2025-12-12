from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    # Главная страница и workspace
    path('', views.workspace, name='workspace'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('demo/', views.ai_demo, name='ai_demo'),  # 🚀 Демо WOW-фич

    
    # API endpoints
    path('records/', views.records_api, name='records_api'),
    path('ai/insights/', views.ai_insights_api, name='ai_insights_api'),
    path('api/dashboard/data/', views.dashboard_data_api, name='dashboard_data_api'),
    path('api/upload/', views.upload_api, name='upload_api'),
    path('ai/chat/', views.ai_chat_api, name='ai_chat_api'),
    
    # 🚀 NEW: WOW-FEATURES для хакатона
    path('api/ai/chat/v2/', views.ai_chat_api_v2, name='ai_chat_v2'),  # Новый улучшенный API
    path('api/ai/chat/stream/', views.ai_chat_streaming, name='ai_chat_streaming'),  # Streaming ответов
    path('api/ai/confidence/', views.ai_confidence_score, name='ai_confidence'),  # Confidence Score
    path('api/ai/health-score/', views.financial_health_score, name='health_score'),  # Health Score
    path('api/ai/reasoning/', views.ai_explain_reasoning, name='ai_reasoning'),  # Chain of Thought
    
    # Авторизация
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    
    # История чатов и экспорт
    path('api/chat/sessions/', views.chat_sessions_api, name='chat_sessions_api'),
    path('api/chat/sessions/<str:session_id>/', views.chat_history_api, name='chat_history_api'),
    path('api/chat/sessions/<str:session_id>/delete/', views.delete_chat_session, name='delete_chat_session'),
    path('api/chat/sessions/<str:session_id>/clear/', views.clear_chat_session, name='clear_chat_session'),
    path('api/chat/sessions/<str:session_id>/rename/', views.rename_chat_session, name='rename_chat_session'),
    path('api/chat/sessions/<str:session_id>/export/', views.export_chat_history, name='export_chat_history'),
    path('api/chat/sessions/<str:session_id>/export/md/', views.export_chat_markdown, name='export_chat_markdown'),
    path('api/chat/sessions/<str:session_id>/advice/complete/', views.mark_advice_completed, name='mark_advice_completed'),
    path('api/chat/messages/<int:message_id>/useful/', views.mark_message_useful, name='mark_message_useful'),
    path('api/chat/stats/', views.get_action_stats, name='get_action_stats'),
    path('api/chat/stats/<str:session_id>/', views.get_action_stats, name='get_action_stats_session'),

    # Настройки и приватность
    path('api/user/settings/', views.user_settings_api, name='user_settings_api'),
    path('api/delete-all/', views.delete_all_data_api, name='delete_all_data_api'),
    path('api/export/all/', views.export_all_data_api, name='export_all_data_api'),
    
    # Управление файлами
    path('api/files/', views.uploaded_files_api, name='uploaded_files_api'),
    path('api/files/<int:file_id>/delete/', views.delete_uploaded_file, name='delete_uploaded_file'),
    path('api/files/<int:file_id>/delete-transactions/', views.delete_transactions_by_file, name='delete_transactions_by_file'),
    path('api/files/delete-transactions/', views.delete_transactions_by_files, name='delete_transactions_by_files'),
    path('api/duplicates/find/', views.find_duplicates_api, name='find_duplicates_api'),
    path('api/duplicates/delete/', views.delete_duplicates_api, name='delete_duplicates_api'),
    path('api/chat/compare/', views.compare_chats_api, name='compare_chats_api'),
    
    # Доходы
    path('income/', views.IncomeListView.as_view(), name='income_list'),
    path('income/create/', views.IncomeCreateView.as_view(), name='income_create'),
    path('income/<int:pk>/edit/', views.IncomeUpdateView.as_view(), name='income_edit'),
    path('income/<int:pk>/delete/', views.IncomeDeleteView.as_view(), name='income_delete'),
    path('income/export/csv/', views.export_income_csv, name='income_export_csv'),

    # Расходы
    path('expense/', views.ExpenseListView.as_view(), name='expense_list'),
    path('expense/create/', views.ExpenseCreateView.as_view(), name='expense_create'),
    path('expense/<int:pk>/edit/', views.ExpenseUpdateView.as_view(), name='expense_edit'),
    path('expense/<int:pk>/delete/', views.ExpenseDeleteView.as_view(), name='expense_delete'),
    path('expense/export/csv/', views.export_expense_csv, name='expense_export_csv'),

    # События
    path('events/', views.EventListView.as_view(), name='event_list'),
    path('events/create/', views.EventCreateView.as_view(), name='event_create'),
    path('events/<int:pk>/edit/', views.EventUpdateView.as_view(), name='event_edit'),
    path('events/<int:pk>/delete/', views.EventDeleteView.as_view(), name='event_delete'),

    # Документы
    path('documents/', views.DocumentListView.as_view(), name='document_list'),
    path('documents/create/', views.DocumentCreateView.as_view(), name='document_create'),
    path('documents/<int:pk>/edit/', views.DocumentUpdateView.as_view(), name='document_edit'),
    path('documents/<int:pk>/delete/', views.DocumentDeleteView.as_view(), name='document_delete'),

    # AI рекомендации
    path('ai/', views.ai_recommendations, name='ai_recommendations'),
    path('documents/generate/', views.document_generate_view, name='document_generate'),
]

