#---------------------------------------------------------------------
# 
# licensed under the terms of GNU GPL 2
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# 
#---------------------------------------------------------------------

import os,sys
sys.path.append("/usr/share/qgis/python")
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *

from ui_control import ui_Control
import resources
from math import *
from getcoordtool import *

class qgsazimuth (object):
    """
    Base class for the qgsAzimuth plugin
    - Provides a means to draw a feature by specifying the angle and distance beetween points.
    - Supports angles in either the conventional 0.0 - 360.0 clockwise from North
        or the surveyor's 'Easting' system with bearings plus or minus 90 deg. from North or South
    - Supports magnetic declination as degrees plus or minus for East or West respectively
    - supports inputs in feet or the current CRS units
    """

    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.fPath = QString()  # set default working directory, updated from config file & by Import/Export
        self.settings = QSettings()
        self.loadConf() # get config data
    
    def initGui(self):
        # create action that will start plugin configuration
        self.action = QAction(QIcon(":qgsazimuth.png"), "Azimuth and distance", self.iface.mainWindow())
        self.action.setWhatsThis("Azimuth and distance")
        QObject.connect(self.action, SIGNAL("activated()"), self.run)
        
        # add toolbar button and menu item
        #self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Topography", self.action)
        
        self.tool = GetCoordTool(self.canvas)

    def unload(self):
        # remove the plugin menu item and icon
        self.iface.removePluginMenu("&Topography",self.action)
        self.iface.removeToolBarIcon(self.action)
        self.saveConf()

    def run(self):
        # create and show a configuration dialog or something similar
        flags = Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMaximizeButtonHint  # QgisGui.ModalDialogFlags
        self.pluginGui = ui_Control(self.iface.mainWindow())

        #INSERT EVERY SIGNAL CONECTION HERE!
        QObject.connect(self.pluginGui.pushButton_vertexInsert,SIGNAL("clicked()"),self.newVertex) 
        QObject.connect(self.pluginGui.pushButton_segListRowDel,SIGNAL("clicked()"),self.delrow) 
        QObject.connect(self.pluginGui.pushButton_segListLoad,SIGNAL("clicked()"),self.loadList)
        QObject.connect(self.pluginGui.pushButton_segListClear,SIGNAL("clicked()"),self.clearList) 
        QObject.connect(self.pluginGui.pushButton_objectDraw,SIGNAL("clicked()"),self.addgeometry)
        QObject.connect(self.pluginGui.pushButton_startCapture,SIGNAL("clicked()"),self.startgetpoint) 
        QObject.connect(self.pluginGui.pushButton_segListSave,SIGNAL("clicked()"),self.saveList)
        
        #fill combo box with all layers
        self.layermap=QgsMapLayerRegistry.instance().mapLayers()
        activeName = ""
        for (name,layer) in self.layermap.iteritems():
            self.pluginGui.comboBox_layers.addItem(name)
            if (layer == self.iface.activeLayer()):
                self.pluginGui.lineEdit_crs.setText((layer.srs()).description())
                #self.say('found active layer='+name)
                activeName = name
                
        
        # set combo box to current active layer
        lyrNdx = self.pluginGui.comboBox_layers.findText(activeName)
        self.pluginGui.comboBox_layers.setCurrentIndex(lyrNdx)
        self.pluginGui.table_segmentList.setCurrentCell(0,0)
        self.pluginGui.show()
        
        #misc init
        self.magDev = 0.0
        
    #Now these are the SLOTS
    def nextvertex(self,v,d,az,zen=90):
        print "direction:", az, zen, d
        az=radians(az)
        zen=radians(zen)
        d1=d*sin(zen)
        x=v[0]+d1*sin(az)
        y=v[1]+d1*cos(az)
        z=v[2]+d*cos(zen)
        print "point ", x,y,z
        return [x,y,z]
    
    def addgeometry(self):
        #reading a layer
        print "Saving in "+self.pluginGui.comboBox_layers.currentText()
        vectorlayer=self.layermap[self.pluginGui.comboBox_layers.currentText()]
        provider=vectorlayer.dataProvider()
        geometrytype=provider.geometryType()
        print geometrytype
        
        #check if the layer is editable
        if (not vectorlayer.isEditable()):
            self.say("Layer not in edit mode.")
            return 0
        
        # if magnetic heading chosen, assure we have a declination angle
        if (self.pluginGui.radioButton_magNorth.isChecked())  and (str(self.pluginGui.lineEdit_magNorth.text()) == ''):   #magnetic headings      
            self.say("No magnetic declination value entered.")
            return 0
        
        vlist=[]
        #Enter starting point
        vlist.append([float(str(self.pluginGui.lineEdit_vertexX0.text())),
                          float(str(self.pluginGui.lineEdit_vertexY0.text())), 
                          float(str(self.pluginGui.lineEdit_vertexZ0.text()))])
        #convert segment list to set of vertice
        for i in range(self.pluginGui.table_segmentList.rowCount()):
            az=str(self.pluginGui.table_segmentList.item(i,0).text())
            dis=float(str(self.pluginGui.table_segmentList.item(i,1).text()))
            zen=str(self.pluginGui.table_segmentList.item(i,2).text())

            if (self.pluginGui.radioButton_englishUnits.isChecked()):
                # adjust for input in feet, not meters
                dis = float(dis)/3.281
           
            #checking degree input
            if (self.pluginGui.radioButton_azimuthAngle.isChecked()):
                az=float(self.dmsToDd(az))
                zen=float(self.dmsToDd(zen))
            elif (self.pluginGui.radioButton_bearingAngle.isChecked()): 
                az=float(self.bearingToDd(az))
                zen=float(self.bearingToDd(zen))
        
            #correct for magnetic compass headings if necessary
            if (self.pluginGui.radioButton_defaultNorth.isChecked()):
                self.magDev = 0.0
            elif (self.pluginGui.radioButton_magNorth.isChecked()): 
                self.magDev = float(self.dmsToDd(str(self.pluginGui.lineEdit_magNorth.text())))
            az = float(az) + float(self.magDev)
        
            #correct for angles outside of 0.0-360.0
            while (az > 360.0):
                az = az - 360.0
            while (az < 0.0):
                az = az + 360.0
        
            #checking survey type
            if (self.pluginGui.radioButton_irrSurvey.isChecked()):
                vlist.append(self.nextvertex(vlist[0],dis,az,zen))      #reference first vertex
                surveytype='irradiation'
            elif (self.pluginGui.radioButton_polySurvey.isChecked()): 
                vlist.append(self.nextvertex(vlist[-1],dis,az,zen))     #reference last vertex
                surveytype = 'polygonal'
    
        #reprojecting to projects SRS
        vlist=self.reproject(vlist, vectorlayer)
        
        featurelist=[]
        if (geometrytype==1): #POINT
            for point in vlist:
                #writing new feature
                p=QgsPoint(point[0],point[1])
                geom=QgsGeometry.fromPoint(p)
                feature=QgsFeature()
                feature.setGeometry(geom)
                featurelist.append(feature)
        elif (geometrytype==2): #LINESTRING
            if (surveytype== 'polygonal'):
                pointlist=[]
                for point in vlist:
                    #writing new feature
                    p=QgsPoint(point[0],point[1])
                    pointlist.append(p)
                geom=QgsGeometry.fromPolyline(pointlist)
                feature=QgsFeature()
                feature.setGeometry(geom)
                featurelist.append(feature)
            elif (surveytype=='irradiation'):
                v0=vlist.pop(0)
                v0=QgsPoint(v0[0],v0[1])
                for point in vlist:
                    #writing new feature
                    p=QgsPoint(point[0],point[1])
                    pointlist=[v0,p]
                    geom=QgsGeometry.fromPolyline(pointlist)
                    feature=QgsFeature()
                    feature.setGeometry(geom)
                    featurelist.append(feature)
        elif (geometrytype==3): #POLYGON
            pointlist=[]
            for point in vlist:
                #writing new feature
                p=QgsPoint(point[0],point[1])
                pointlist.append(p)
            geom=QgsGeometry.fromPolygon([pointlist])
            feature=QgsFeature()
            feature.setGeometry(geom)
            featurelist.append(feature)
        
        #commit
        vectorlayer.addFeatures(featurelist)
        self.iface.mapCanvas().zoomToSelected()
        
    def bearingToDd (self,  dms):
        #allow survey bearings in form:  - N 25d 34' 40" E
        #where minus ('-') sign allows handling bearings given in reverse direction
        dms = dms.strip()
        if (dms[0] == '-'):
            rev = True
            dms = dms[1:].strip()
        else:
            rev = False
        
        baseDir = dms[0].upper()
        if (baseDir in ['N','S']):
            adjDir = dms[-1].upper()
            bearing = True
            if (baseDir == 'N'):
                if (adjDir == 'E'):
                    base = 0.0
                    adj = 'add'
                elif (adjDir == 'W'):
                    base = 360.0
                    adj = 'sub'
                else:
                    return 0
            elif (baseDir == 'S'):
                base = 180.0
                if (adjDir == 'E'):
                    adj = 'sub'
                elif (adjDir == 'W'):
                    adj = 'add'
                else:
                    return 0
        else:
            bearing = False

        dd = self.dmsToDd(dms)
 
        if (rev):
            dd = float(dd)+180.0
        
        if (bearing == True):
            if (adj == 'add'):
                dd = float(base) + float(dd)
            elif (adj == 'sub'):
                dd = float(base) - float(dd)

        return dd
 
    def dmsToDd(self,dms):
        "It's not fast, but it's a safe way of dealing with DMS"
        dms=dms.replace(" ", "")
        for c in dms:
            if ((not c.isdigit()) and (c != '.') and (c != '-')):
                dms=dms.replace(c,';')
        while (dms.find(";;")>=0):
            dms=dms.replace(";;",';')
        if dms[0]==';':
            dms=dms[1:]
        dms=dms.split(";")
        dd=0
        #dd=str(float(dms[0])+float(dms[1])/60+float(dms[2])/3600)
        for i, f in enumerate(dms):
            if f!="":
                dd+=float(f)/pow(60, i)
        return dd
    
    def clearList(self):
        self.pluginGui.table_segmentList.clearContents()
        self.pluginGui.table_segmentList.setRowCount(0)
    
    def newVertex(self):
        #adds a vertex from the gui
        self.addrow(self.pluginGui.lineEdit_nextAzimuth.text(), 
                        self.pluginGui.lineEdit_nextDistance.text(), 
                        self.pluginGui.lineEdit_nextVertical.text())
    
    def addrow(self, az=0, dist=0, zen=90):
        #insert the vertext in the table
        if (self.pluginGui.table_segmentList.currentRow()>0):
            i=self.pluginGui.table_segmentList.currentRow()
        else:
            i=self.pluginGui.table_segmentList.rowCount()
        self.pluginGui.table_segmentList.insertRow(i)
        self.pluginGui.table_segmentList.setItem(i, 0, QTableWidgetItem(str(az)))
        self.pluginGui.table_segmentList.setItem(i, 1, QTableWidgetItem(str(dist)))
        self.pluginGui.table_segmentList.setItem(i, 2, QTableWidgetItem(str(zen)))
    
    def delrow(self):
        self.pluginGui.table_segmentList.removeRow(self.pluginGui.table_segmentList.currentRow())
    
    def moveup(self):
        pass
    
    def movedown(self):
        pass
    
    def startgetpoint(self):
        #point capture tool
        QObject.connect(self.tool, SIGNAL("finished(PyQt_PyObject)"), self.getpoint)
        self.saveTool = self.canvas.mapTool()
        self.canvas.setMapTool(self.tool)

    def getpoint(self,pt):
        self.pluginGui.lineEdit_vertexX0.setText(str(pt.x()))
        self.pluginGui.lineEdit_vertexY0.setText(str(pt.y()))
        self.canvas.setMapTool(self.saveTool)
        QObject.disconnect(self.tool, SIGNAL("finished(PyQt_PyObject)"), self.getpoint)

    def reproject(self, vlist,  vectorlayer):
        renderer=self.canvas.mapRenderer()
        for i, point in enumerate(vlist):
            vlist[i]= renderer.layerToMapCoordinates(vectorlayer, QgsPoint(point[0], point[1]))
        return vlist

    def setAngle(self, s):
        #self.say('processing angleType='+s)
        if (s=='azimuth'):
            self.pluginGui.radioButton_azimuthAngle.setChecked(True)
        elif (s=='bearing'):
            self.pluginGui.radioButton_bearingAngle.setChecked(True)
        elif (s=='polar'):
            self.pluginGui.radioButton_polorCoordAngle.setChecked(True)
        else:
            self.say('invalid angle type: '+s)
    
    def setHeading(self,  s):
        #self.say('processing headingType='+s)
        if (s=='coordinate system'):
            self.pluginGui.radioButton_defaultNorth.setChecked(True)
        elif (s=='magnetic'):
            self.pluginGui.radioButton_magNorth.setChecked(True)
        else:
            self.say('invalid heading type: '+s)
            
    def setDeclination(self,  s):    
        #self.say('processing declination='+s)
        self.pluginGui.lineEdit_magNorth.setText(s)
        self.magDev = float(s)

    def setDistanceUnits(self,  s):
         #self.say('processing distance units='+s)
        if (s=='feet'):
            self.pluginGui.radioButton_englishUnits.setChecked(True)
        else:
            self.pluginGui.radioButton_defaultUnits.setChecked(True)

    def setStartAt(self,  s):
        #self.say('processing startAt='+s)
        coords=s.split(';')
        self.pluginGui.lineEdit_vertexX0.setText(coords[0])
        self.pluginGui.lineEdit_vertexY0.setText(coords[1])
        self.pluginGui.lineEdit_vertexZ0.setText(coords[2])
    
    def setSurvey(self, s):
        #self.say('processing surveyType='+s)
        if (s=='polygonal'):
            self.pluginGui.radioButton_polySurvey.setChecked(True)
        elif (s=='irradiate'):
            self.pluginGui.radioButton_irrSurvey.setChecked(True)
        else:
            self.say('invalid survey type: '+s)
    
    def say(self, txt):
        warn=QgsMessageViewer()
        warn.setMessageAsPlainText(txt)
        warn.showMessage()
    
    # ---------------------------------------------------------------------------------------------------------------------------------
    #               File handling
    # This section deals with saving the user data to disk, and loading it
    #
    # format:
    #   line 1: angle=Azimuth|Bearing|Polar
    #   line 2: heading=Coordinate System|Magnetic
    #   line 3: declination=[- ]x.xxd[ xx.x'] [E|W]
    #   line 4: distunits=Default|Feet
    #   line 5: startAt=xxxxx.xxxxx, xxxxxx.xxxxx
    #   line 6: survey=Polygonal|Irradiat
    #   line 7: [data]
    #   line 8 through end: Azimuth; dist; zen
    #
    #       note: lines 1 through 5 are optional if hand entered, but will always be generated when 'saved'
    # ---------------------------------------------------------------------------------------------------------------------------------
    def loadList(self):
        file=QFileDialog.getOpenFileName(None,"Load data separated by ';'",self.fPath,QString(),None)
        if not os.path.exists(file):
            return 0
        # update selected file's folder
        fInfo = QFileInfo(file)
        self.fPath = fInfo.absolutePath ()
        self.saveConf()

        # get saved data
        f=open(file)
        lines=f.readlines()
        f.close()
        for line in lines:
            #remove trailing 'new lines', etc and break into parts
            parts = ((line.strip()).lower()).split("=")
            if (len(parts)>1):
                #self.say("line="+line+'\nparts[0]='+parts[0]+'\nparts[1]='+parts[1])
                if (parts[0].lower()=='angle'):
                    self.setAngle(parts[1].lower())
                elif (parts[0].lower()=='heading'):
                    self.setHeading(parts[1].lower())
                elif (parts[0].lower()=='declination'):
                    self.setDeclination(parts[1].lower())
                elif (parts[0].lower()=='dist_units'):
                    self.setDistanceUnits(parts[1].lower())
                elif (parts[0].lower()=='startat'):
                    self.setStartAt(parts[1].lower())
                elif (parts[0].lower()=='survey'):
                    self.setSurvey(parts[1].lower())
            else:
                coords=(line.strip()).split(";")
                if (coords[0].lower()=='[data]'):
                    pass
                else:
                    self.addrow(coords[0], coords[1], coords[2])
   
    def saveList(self):
        file=QFileDialog.getSaveFileName(None,"Save segment list to file.",self.fPath,QString(),None)
        f=open(file, 'w')
        # update selected file's folder
        fInfo = QFileInfo(file)
        self.fPath = fInfo.absolutePath ()
        self.saveConf()
        
        if (self.pluginGui.radioButton_azimuthAngle.isChecked()): 
            s='Azimuth'
        elif (self.pluginGui.radioButton_bearingAngle.isChecked()):
            s='Bearing'
        f.write('angle='+s+'\n') 
        
        if (self.pluginGui.radioButton_defaultNorth.isChecked()):
            s='Coordinate_System'
        elif (self.pluginGui.radioButton_magNorth.isChecked()):
            s='Magnetic'
        f.write('heading='+s+'\n') 
        
        if (self.magDev!=0.0):
            f.write('declination='+str(self.magDev)+'\n')
        
        if (self.pluginGui.radioButton_defaultUnits.isChecked()):
            s='Default'
        elif (self.pluginGui.radioButton_englishUnits.isChecked()):
            s='Feet'
        f.write('dist_units='+s+'\n') 
        
        f.write('startAt='+str(self.pluginGui.lineEdit_vertexX0.text())+';'+
                                    str(self.pluginGui.lineEdit_vertexY0.text())+';'+
                                    str(self.pluginGui.lineEdit_vertexZ0.text())+'\n')

        if (self.pluginGui.radioButton_polySurvey.isChecked()):
            s='Polygonal'
        elif (self.pluginGui.radioButton_irrSurvey.isChecked()):
            s='Irradiate'
        f.write('survey='+s+'\n') 
        
        f.write('[data]\n')
        for i in range(self.pluginGui.table_segmentList.rowCount()):
            line = str(self.pluginGui.table_segmentList.item(i, 0).text()) +';' \
                    +str(self.pluginGui.table_segmentList.item(i, 1).text()) +';' \
                    +str(self.pluginGui.table_segmentList.item(i, 2).text())
            f.write(line+'\n')
            
        f.close()
    
    #------------------------
    def loadConf(self):
        settings=QSettings()
        self.fPath = settings.value('/Plugin-qgsAzimuth/inp_exp_dir').toString()
        

    def saveConf(self):
        settings=QSettings()
        settings.setValue('/Plugin-qgsAzimuth/inp_exp_dir', QVariant(self.fPath))
