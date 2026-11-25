from setuptools import setup

setup(
    data_files=[
        ('examples', [f'examples/{name}' for name in __import__('os').listdir('examples')]),
        ('head-demo', [f'head-demo/{name}' for name in __import__('os').listdir('head-demo')]),
        ('share/stl-assembly', ['README.md', 'MACHINING.md', 'ACCEPTANCE.md', 'DELIVERY-AUDIT.md', 'DELIVERY-RECHECK.md', 'frame-example.json', 'requirements.txt']),
    ],
    package_data={'': ['*.md']},
)
