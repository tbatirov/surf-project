from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('transaction_mapper', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='debit_account',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name='debit_transactions',
                to='transaction_mapper.account',
                help_text='Account to be debited'
            ),
        ),
        migrations.AddField(
            model_name='transaction',
            name='credit_account',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name='credit_transactions',
                to='transaction_mapper.account',
                help_text='Account to be credited'
            ),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='mapped_account',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name='legacy_mapped_transactions',
                to='transaction_mapper.account',
                help_text='Legacy field - use debit_account and credit_account instead'
            ),
        ),
    ]
