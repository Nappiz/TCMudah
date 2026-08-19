"""
Unit tests for app.crud.crud_notifications.

Target: app.crud.crud_notifications
"""

import pytest
from unittest.mock import MagicMock

from app.crud.crud_notifications import get_notifications_summary

class TestCrudNotifications:
    def test_get_notifications_summary_no_last_seen(self, mock_supabase):
        """Test when no last_seen parameters are provided (only orders should be checked)."""
        def mock_table_side_effect(table_name):
            mock_tbl = MagicMock()
            mock_sel = MagicMock()
            mock_tbl.select.return_value = mock_sel
            
            if table_name == "orders":
                mock_sel.eq.return_value.execute.return_value = MagicMock(count=5)
                
            return mock_tbl
            
        mock_supabase.table.side_effect = mock_table_side_effect
        
        result = get_notifications_summary()
        
        assert result["new_orders"] == 5
        assert result["new_users"] == 0
        assert result["new_feedbacks"] == 0
        
        mock_supabase.table.assert_called_once_with("orders")

    def test_get_notifications_summary_with_last_seen(self, mock_supabase):
        """Test when last_seen parameters are provided (users and feedbacks should be checked)."""
        def mock_table_side_effect(table_name):
            mock_tbl = MagicMock()
            mock_sel = MagicMock()
            mock_tbl.select.return_value = mock_sel
            
            if table_name == "orders":
                mock_sel.eq.return_value.execute.return_value = MagicMock(count=2)
            elif table_name == "users":
                mock_sel.gt.return_value.execute.return_value = MagicMock(count=10)
            elif table_name == "feedbacks":
                mock_sel.gt.return_value.execute.return_value = MagicMock(count=3)
                
            return mock_tbl
            
        mock_supabase.table.side_effect = mock_table_side_effect
        
        result = get_notifications_summary(
            last_seen_users="2023-01-01T00:00:00Z", 
            last_seen_feedbacks="2023-01-01T00:00:00Z"
        )
        
        assert result["new_orders"] == 2
        assert result["new_users"] == 10
        assert result["new_feedbacks"] == 3
        
        assert mock_supabase.table.call_count == 3
