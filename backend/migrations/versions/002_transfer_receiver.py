"""Record the person receiving a stock transfer."""
from alembic import op
import sqlalchemy as sa

revision = '002_transfer_receiver'
down_revision = '587dbf81191c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('transfers', sa.Column('received_by', sa.String(80), nullable=True))


def downgrade():
    op.drop_column('transfers', 'received_by')
