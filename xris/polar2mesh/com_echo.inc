      implicit real *8 (a-h,o-z)
      implicit integer *4 (i-n)

      common /radar/  np,nr,dr,dp,oset,azi(0:1000),ele(0:1000)   ! azi(p),ele(p)
      common /site/   xr,yr
      common /rain/   xmp(0:10000,0:10000),rr(-5000:5000,-5000:5000)
      common /phase/  azmin(0:1000),a(0:1000),xmpmin(0:1000,0:1000)
      Common /inter/  reso
