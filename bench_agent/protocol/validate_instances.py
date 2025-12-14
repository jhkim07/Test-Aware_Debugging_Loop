"""
인스턴스 ID 유효성 검증 유틸리티
"""
from __future__ import annotations


def validate_instance_ids(dataset_name: str, instance_ids: list[str]) -> tuple[list[str], list[str]]:
    """
    인스턴스 ID 유효성 검증
    
    Args:
        dataset_name: SWE-bench 데이터셋 이름
        instance_ids: 검증할 인스턴스 ID 목록
    
    Returns:
        (valid_ids, invalid_ids) 튜플
    """
    try:
        from datasets import load_dataset
        
        ds = load_dataset(dataset_name, split='test')
        valid_ids_set = {item['instance_id'] for item in ds}
        
        valid = [id for id in instance_ids if id in valid_ids_set]
        invalid = [id for id in instance_ids if id not in valid_ids_set]
        
        return valid, invalid
    except Exception as e:
        # 데이터셋 로드 실패 시 검증 건너뜀 (경고만 출력)
        import warnings
        warnings.warn(f"Instance ID validation failed: {e}. Proceeding without validation.")
        return instance_ids, []

