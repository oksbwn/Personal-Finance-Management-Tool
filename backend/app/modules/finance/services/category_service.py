from typing import List, Optional, Dict
import json
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.modules.finance import models, schemas

class CategoryService:
    # --- Category Management ---
    @staticmethod
    def get_categories(db: Session, tenant_id: str) -> List[models.Category]:
        cats = db.query(models.Category).filter(models.Category.tenant_id == tenant_id).all()
        if not cats:
            # Seed defaults
            defaults = [
                ("Food & Dining", "🍔"), ("Groceries", "🥦"), ("Transport", "🚌"), 
                ("Shopping", "🛍️"), ("Utilities", "💡"), ("Housing", "🏠"),
                ("Healthcare", "🏥"), ("Entertainment", "🎬"), ("Salary", "💰"),
                ("Investment", "📈"), ("Education", "🎓"), ("Dividend", "💵"),
                ("FD Matured", "🏦"), ("Rent", "🏘️"), ("Gift", "🎁"),
                 ("Other", "📦")
            ]
            new_cats = []
            for name, icon in defaults:
                c = models.Category(tenant_id=tenant_id, name=name, icon=icon)
                db.add(c)
                new_cats.append(c)
            db.commit()
            return new_cats
        return cats

    @staticmethod
    def create_category(db: Session, category: schemas.CategoryCreate, tenant_id: str) -> models.Category:
        db_cat = models.Category(
            **category.model_dump(),
            tenant_id=tenant_id
        )
        db.add(db_cat)
        db.commit()
        db.refresh(db_cat)
        return db_cat

    @staticmethod
    def update_category(db: Session, category_id: str, update: schemas.CategoryUpdate, tenant_id: str) -> Optional[models.Category]:
        db_cat = db.query(models.Category).filter(models.Category.id == category_id, models.Category.tenant_id == tenant_id).first()
        if not db_cat: return None
        
        data = update.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(db_cat, k, v)
            
        db.commit()
        db.refresh(db_cat)
        return db_cat

    @staticmethod
    def delete_category(db: Session, category_id: str, tenant_id: str) -> bool:
        db_cat = db.query(models.Category).filter(models.Category.id == category_id, models.Category.tenant_id == tenant_id).first()
        if not db_cat: return False
        db.delete(db_cat)
        db.commit()
        return True

    # --- Rules ---
    @staticmethod
    def create_category_rule(db: Session, rule: schemas.CategoryRuleCreate, tenant_id: str) -> models.CategoryRule:
        data = rule.model_dump()
        if isinstance(data.get('keywords'), list):
            data['keywords'] = json.dumps(data['keywords'])
            
        db_rule = models.CategoryRule(
            **data,
            tenant_id=tenant_id
        )
             
        db.add(db_rule)
        db.commit()
        db.refresh(db_rule)
        
        # Manually deserialize keywords for Pydantic response
        try:
             db_rule.keywords = json.loads(db_rule.keywords)
        except:
             db_rule.keywords = []
             
        return db_rule

    @staticmethod
    def get_category_rules(db: Session, tenant_id: str) -> List[models.CategoryRule]:
        rules = db.query(models.CategoryRule).filter(models.CategoryRule.tenant_id == tenant_id).order_by(models.CategoryRule.priority.desc()).all()
        for r in rules:
             try:
                 r.keywords = json.loads(r.keywords)
             except:
                 r.keywords = []
        return rules

    @staticmethod
    def update_category_rule(db: Session, rule_id: str, rule_update: schemas.CategoryRuleUpdate, tenant_id: str) -> Optional[models.CategoryRule]:
        db_rule = db.query(models.CategoryRule).filter(
            models.CategoryRule.id == rule_id,
            models.CategoryRule.tenant_id == tenant_id
        ).first()
        
        if not db_rule:
            return None
            
        update_data = rule_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == 'keywords' and value is not None:
                setattr(db_rule, key, json.dumps(value))
            else:
                setattr(db_rule, key, value)
                
        db.commit()
        db.refresh(db_rule)
        
        # Deserialize for response
        try:
             db_rule.keywords = json.loads(db_rule.keywords)
        except:
             db_rule.keywords = []
             
        return db_rule

    @staticmethod
    def delete_category_rule(db: Session, rule_id: str, tenant_id: str) -> bool:
        db_rule = db.query(models.CategoryRule).filter(
            models.CategoryRule.id == rule_id,
            models.CategoryRule.tenant_id == tenant_id
        ).first()
        
        if not db_rule:
            return False
            
        db.delete(db_rule)
        db.commit()
        return True

    @staticmethod
    def ignore_suggestion(db: Session, pattern: str, tenant_id: str):
        exists = db.query(models.IgnoredSuggestion).filter(
            models.IgnoredSuggestion.tenant_id == tenant_id,
            models.IgnoredSuggestion.pattern == pattern
        ).first()
        if not exists:
            db.add(models.IgnoredSuggestion(tenant_id=tenant_id, pattern=pattern))
            db.commit()
            
    @staticmethod
    def get_rule_suggestions(db: Session, tenant_id: str) -> List[dict]:
        """
        Analyze transaction history to suggest new rules.
        """
        # Group by Description + Category
        results = db.query(
            models.Transaction.description,
            models.Transaction.category,
            func.count(models.Transaction.id).label("count")
        ).filter(
            models.Transaction.tenant_id == tenant_id,
            models.Transaction.category != "Uncategorized",
            models.Transaction.category != None
        ).group_by(
            models.Transaction.description, 
            models.Transaction.category
        ).having(
            func.count(models.Transaction.id) >= 1
        ).order_by(
            func.count(models.Transaction.id).desc()
        ).limit(10).all()
        
        suggestions = []
        existing_rules = db.query(models.CategoryRule).filter(models.CategoryRule.tenant_id == tenant_id).all()
        ignored = db.query(models.IgnoredSuggestion).filter(models.IgnoredSuggestion.tenant_id == tenant_id).all()
        
        # Flatten existing keywords for basic dedup
        existing_keywords = set()
        for r in existing_rules:
            try:
                kw = json.loads(r.keywords)
                for k in kw: existing_keywords.add(k.lower())
            except: pass
            
        for i in ignored:
            existing_keywords.add(i.pattern.lower())

        for row in results:
            desc = row.description
            cat = row.category
            count = row.count
            
            if desc.lower() in existing_keywords:
                continue
                
            suggestions.append({
                "name": f"Auto-tag {desc}",
                "category": cat,
                "keywords": [desc], 
                "confidence": count
            })
            
        return suggestions
