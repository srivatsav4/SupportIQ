"""SQLAlchemy models for the synthetic NovaCart database and platform tables."""
from datetime import datetime
from sqlalchemy import (Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index)
from sqlalchemy.orm import relationship
from app.database.session import Base


class Customer(Base):
    __tablename__ = "customers"
    customer_id = Column(String(20), primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(160), unique=True, nullable=False, index=True)
    phone = Column(String(30))
    membership_tier = Column(String(20), default="Silver")
    role = Column(String(20), default="CUSTOMER")   # CUSTOMER | SUPPORT_AGENT | ADMIN
    password_hash = Column(String(300))
    created_at = Column(DateTime, default=datetime.utcnow)
    orders = relationship("Order", back_populates="customer")


class Product(Base):
    __tablename__ = "products"
    product_id = Column(String(20), primary_key=True)
    name = Column(String(160), nullable=False)
    category = Column(String(60), index=True)
    price = Column(Float, nullable=False)
    inventory = Column(Integer, default=0)
    description = Column(Text)
    warranty_period = Column(Integer, default=0)  # months


class Order(Base):
    __tablename__ = "orders"
    order_id = Column(String(20), primary_key=True)
    customer_id = Column(String(20), ForeignKey("customers.customer_id"), index=True)
    order_date = Column(DateTime)
    status = Column(String(30), index=True)
    total_amount = Column(Float)
    shipping_address = Column(String(300))
    expected_delivery = Column(DateTime)
    delivered_at = Column(DateTime, nullable=True)
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    order_item_id = Column(String(24), primary_key=True)
    order_id = Column(String(20), ForeignKey("orders.order_id"), index=True)
    product_id = Column(String(20), ForeignKey("products.product_id"))
    quantity = Column(Integer)
    price = Column(Float)
    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class Payment(Base):
    __tablename__ = "payments"
    payment_id = Column(String(20), primary_key=True)
    order_id = Column(String(20), ForeignKey("orders.order_id"), index=True)
    payment_method = Column(String(30))
    card_last4 = Column(String(4), nullable=True)
    amount = Column(Float)
    status = Column(String(20))          # Success | Failed | Pending | Refunded
    transaction_reference = Column(String(40))
    created_at = Column(DateTime)


class Refund(Base):
    __tablename__ = "refunds"
    refund_id = Column(String(20), primary_key=True)
    order_id = Column(String(20), ForeignKey("orders.order_id"), index=True)
    amount = Column(Float)
    reason = Column(String(200))
    status = Column(String(20))          # Initiated | Approved | Completed | Rejected
    initiated_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)


class Shipment(Base):
    __tablename__ = "shipments"
    shipment_id = Column(String(20), primary_key=True)
    order_id = Column(String(20), ForeignKey("orders.order_id"), index=True)
    carrier = Column(String(40))
    tracking_number = Column(String(40))
    status = Column(String(30))          # Label Created | In Transit | Out for Delivery | Delivered | Exception | Lost
    expected_delivery = Column(DateTime)
    last_update = Column(DateTime)


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    ticket_id = Column(String(24), primary_key=True)
    customer_id = Column(String(20), ForeignKey("customers.customer_id"), index=True)
    category = Column(String(40))
    priority = Column(String(10), index=True)   # Low | Medium | High | Urgent
    status = Column(String(20), index=True)     # Open | In Progress | Resolved | Closed
    description = Column(Text)
    assigned_agent = Column(String(60), nullable=True)
    order_id = Column(String(20), nullable=True)
    conversation_id = Column(String(40), nullable=True)
    escalation_context = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    conversation_id = Column(String(40), primary_key=True)
    customer_id = Column(String(20), ForeignKey("customers.customer_id"), index=True)
    messages = Column(JSON, default=list)
    intent = Column(String(40))
    sentiment = Column(String(20))
    resolution_status = Column(String(20), default="open")  # open | ai_resolved | escalated
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    total_latency_ms = Column(Float, default=0.0)
    turns = Column(Integer, default=0)
    llm_tokens = Column(Integer, default=0)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    approval_id = Column(String(24), primary_key=True)
    customer_id = Column(String(20), index=True)
    conversation_id = Column(String(40), nullable=True)
    action = Column(String(40))
    params = Column(JSON)
    risk_level = Column(String(10))
    reason = Column(Text)
    status = Column(String(15), default="PENDING", index=True)  # PENDING | APPROVED | REJECTED | EXECUTED | FAILED
    reviewer = Column(String(60), nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class KBChunk(Base):
    __tablename__ = "kb_chunks"
    chunk_id = Column(String(60), primary_key=True)
    document = Column(String(80), index=True)
    section = Column(String(160))
    source = Column(String(160))
    content = Column(Text)
    embedding_json = Column(JSON)  # portable copy; Postgres also gets a pgvector column


class InteractionLog(Base):
    """One row per AI turn: used for analytics and evaluation of the live system."""
    __tablename__ = "interaction_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(40), index=True)
    customer_id = Column(String(20))
    intent = Column(String(40))
    latency_ms = Column(Float)
    rag_latency_ms = Column(Float, default=0.0)
    top_retrieval_score = Column(Float, default=0.0)
    groundedness = Column(Float, default=0.0)
    citation_accuracy = Column(Float, default=1.0)
    verifier_passed = Column(Boolean, default=True)
    escalated = Column(Boolean, default=False)
    tool_calls = Column(Integer, default=0)
    tool_failures = Column(Integer, default=0)
    tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
