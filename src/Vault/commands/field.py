from .base import BaseCommand

class FieldCommand(BaseCommand):

    call_str = "field" # Tells the prompt the string command in order to call this class

    USAGE = """
  field add <category> <name>          Register a new tracked field
  field remove <name>                  Deactivate a field (history preserved)
  field list                           Show all active fields by category
  field set <category> unit <unit>     Set display unit for a category (default: $)
"""

    def entry_point(self, options: list):
        """Function call that prompt will made when user enters in the call_str. This function is responsible for
        directing input to the correct sub commands of this class."""

        # Error handling
        if not options:
            self.usage()
            return
        
        # Business logic
        sub = options[0]
        if sub in self.sub_commands:
            self.sub_commands[sub](options[1:])
        else:
            print(f"Unknown sub command: {sub}")

    ####################################
    # Sub-commands
    ####################################
    def sub_add(self, options: list):
        
        # Error checking
        if len(options) < 2:
            print("Usage: field add <category> <name>")
            return
        category, name = options[0], options[1]
        if " " in name or " " in category:
            print("Field and category names cannot contain spaces.")
            return
        
        # Business logic
        success = self.db.add_field(name, category)
        if success:
            print(f"Field '{name}' added under category '{category}'.")
            self.logger.log(f"Field added: {name} (category: {category})")
        else:
            print(f"Field '{name}' already exists.")

    def sub_remove(self, options: list):

        # Error checking
        if len(options) < 1:
            print("Usage: field remove <name>")
            return
        
        # Business logic
        name = options[0]
        success = self.db.deactivate_field(name)
        if success:
            print(f"Field '{name}' deactivated. History is preserved.")
            self.logger.log(f"Field deactivated: {name}")
        else:
            print(f"No active field named '{name}' found.")

    def sub_list(self, options: list):
        
        # Error checking
        fields = self.db.get_active_fields()
        if not fields:
            print("No active fields. Use 'field add <category> <name>' to add one.")
            return
        
        # Business logic
        current_cat = None
        for field_name, category_name, unit in fields:
            if category_name != current_cat:
                unit_str = f" [{unit}]" if unit != "$" else ""
                print(f"\n  {self.cat_label(category_name)}{unit_str}")
                current_cat = category_name
            print(f"    - {field_name}")
        print()

    def sub_set(self, options: list):
        
        # Error Checking
        if len(options) != 3:
            print("Usage: field set <category> unit <unit>")
            return
        
        # Business logic
        category, prop, value = options[0], options[1], options[2]
        if prop == "unit":
            success = self.db.set_category_unit(category, value)
        else:
            print(f"Unknown property '{prop}'. Supported: unit")
